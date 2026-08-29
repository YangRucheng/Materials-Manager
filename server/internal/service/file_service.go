// Package service 文件服务：图片上传/读取/预览/孤儿清理（等价 file_service.py）。
package service

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"image"
	"image/color"
	stddraw "image/draw"
	"image/png"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/kolesa-team/go-webp/encoder"
	"github.com/kolesa-team/go-webp/webp"
	xdraw "golang.org/x/image/draw"
	_ "golang.org/x/image/webp"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

const (
	acceptedJpeg = "image/jpeg"
	acceptedPng  = "image/png"
	acceptedWebp = "image/webp"
	previewMime  = "image/webp"
)

var managedFileName = regexp.MustCompile(
	`^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.png$`)

var digestLocks sync.Mutex
var digestLockMap = map[string]*digestLockEntry{}

type digestLockEntry struct {
	lock  sync.Mutex
	users int
}

func withDigestLock(digest string, fn func()) {
	digestLocks.Lock()
	entry, ok := digestLockMap[digest]
	if !ok {
		entry = &digestLockEntry{}
		digestLockMap[digest] = entry
	}
	entry.users++
	digestLocks.Unlock()

	entry.lock.Lock()
	defer func() {
		entry.lock.Unlock()
		digestLocks.Lock()
		entry.users--
		if entry.users == 0 {
			delete(digestLockMap, digest)
		}
		digestLocks.Unlock()
	}()
	fn()
}

func filePath(cfg *config.Config, fileID string) string {
	return filepath.Join(cfg.UploadDirPath, fileID+".png")
}

func acceptedImageType(contentType string) bool {
	switch contentType {
	case acceptedJpeg, acceptedPng, acceptedWebp:
		return true
	}
	return false
}

func imageHasAlpha(img image.Image) bool {
	switch img.ColorModel() {
	case color.RGBAModel, color.NRGBAModel, color.AlphaModel,
		color.RGBA64Model, color.NRGBA64Model, color.Alpha16Model:
		return true
	}
	if paletted, ok := img.(*image.Paletted); ok {
		for _, c := range paletted.Palette {
			if _, _, _, a := c.RGBA(); a < 0xffff {
				return true
			}
		}
	}
	return false
}

// decodeAndConvertPNG 解码并转为 PNG（含 alpha 保留 RGBA，否则 RGB）。
func decodeAndConvertPNG(raw []byte) ([]byte, int, int, error) {
	img, _, err := image.Decode(bytes.NewReader(raw))
	if err != nil {
		return nil, 0, 0, err
	}
	bounds := img.Bounds()
	width, height := bounds.Dx(), bounds.Dy()
	hasAlpha := imageHasAlpha(img)
	out := image.NewRGBA(bounds)
	stddraw.Draw(out, bounds, img, bounds.Min, stddraw.Src)
	var target image.Image = out
	if !hasAlpha {
		target = image.NewRGBA(bounds)
		stddraw.Draw(target.(*image.RGBA), bounds, img, bounds.Min, stddraw.Src)
	}
	var buf bytes.Buffer
	enc := png.Encoder{CompressionLevel: png.BestCompression}
	if err := enc.Encode(&buf, target); err != nil {
		return nil, 0, 0, err
	}
	return buf.Bytes(), width, height, nil
}

// SaveImage 保存上传图片：类型校验 -> 转 PNG -> sha256 去重 -> 落盘 + 入库（独立事务）。
func SaveImage(cfg *config.Config, db *gorm.DB, contentType, originalName string, raw []byte) (*models.FileObject, *apperrors.AppError) {
	if !acceptedImageType(contentType) {
		return nil, apperrors.New("INVALID_IMAGE_TYPE", "仅支持 JPEG、PNG 或 WebP 图片", 0, nil)
	}
	if int64(len(raw)) > cfg.MaxImageBytes {
		return nil, apperrors.New("IMAGE_TOO_LARGE", "单张图片不能超过 10 MB", 413, nil)
	}
	data, width, height, err := decodeAndConvertPNG(raw)
	if err != nil {
		return nil, apperrors.New("INVALID_IMAGE", "图片无法解码", 0, nil)
	}
	sum := sha256.Sum256(data)
	digest := hex.EncodeToString(sum[:])
	var result *models.FileObject
	var saveErr error
	withDigestLock(digest, func() {
		result, saveErr = saveImageLocked(cfg, db, data, width, height, digest, originalName)
	})
	if saveErr != nil {
		return nil, DatabaseError(saveErr)
	}
	return result, nil
}

func saveImageLocked(cfg *config.Config, db *gorm.DB, data []byte, width, height int, digest, originalName string) (*models.FileObject, error) {
	var existing []models.FileObject
	if err := db.Where("sha256 = ?", digest).Order("created_at, id").Find(&existing).Error; err != nil {
		return nil, err
	}
	var missingItem *models.FileObject
	for i := range existing {
		item := &existing[i]
		path := filePath(cfg, item.ID)
		if _, statErr := os.Stat(path); os.IsNotExist(statErr) {
			if missingItem == nil {
				missingItem = item
			}
			continue
		}
		if item.SizeBytes != int64(len(data)) {
			continue
		}
		diskData, readErr := os.ReadFile(path)
		if readErr != nil {
			continue
		}
		if bytes.Equal(diskData, data) {
			return item, nil
		}
	}
	_ = os.MkdirAll(cfg.UploadDirPath, 0o755)
	if missingItem != nil {
		target := filePath(cfg, missingItem.ID)
		if err := os.WriteFile(target, data, 0o644); err != nil {
			return nil, err
		}
		updates := map[string]any{
			"mime_type":  "image/png",
			"size_bytes": len(data),
			"width":      width,
			"height":     height,
		}
		if err := db.Model(&models.FileObject{}).Where("id = ?", missingItem.ID).Updates(updates).Error; err != nil {
			_ = os.Remove(target)
			return nil, err
		}
		return missingItem, nil
	}
	fileID := security.UUID7String()
	target := filePath(cfg, fileID)
	if err := os.WriteFile(target, data, 0o644); err != nil {
		return nil, err
	}
	item := models.FileObject{
		ID:           fileID,
		OriginalName: truncateName(originalName),
		MimeType:     "image/png",
		SizeBytes:    int64(len(data)),
		Width:        width,
		Height:       height,
		SHA256:       digest,
		CreatedAt:    models.UTCNow(),
		UpdatedAt:    models.UTCNow(),
		Version:      1,
	}
	if err := db.Create(&item).Error; err != nil {
		_ = os.Remove(target)
		return nil, err
	}
	return &item, nil
}

func truncateName(s string) string {
	base := filepath.Base(s)
	if base == "." || base == "/" || base == "" {
		base = "image"
	}
	if len(base) > 255 {
		base = base[:255]
	}
	return base
}

// GetImage 查询图片记录与磁盘路径。
func GetImage(cfg *config.Config, db *gorm.DB, fileID string) (*models.FileObject, string, *apperrors.AppError) {
	var item models.FileObject
	err := db.Where("id = ?", fileID).First(&item).Error
	if IsNotFound(err) {
		return nil, "", apperrors.NotFound("图片")
	}
	if err != nil {
		return nil, "", DatabaseError(err)
	}
	path := filePath(cfg, fileID)
	if _, statErr := os.Stat(path); os.IsNotExist(statErr) {
		return nil, "", apperrors.New("FILE_MISSING", "图片文件不存在", 0, nil)
	}
	return &item, path, nil
}

// RenderPreview 生成 size 缩略图的 WebP 预览（质量 82，LANCZOS 近似 CatmullRom）。
func RenderPreview(sourcePath string, size int) ([]byte, error) {
	f, err := os.Open(sourcePath)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	src, _, err := image.Decode(f)
	if err != nil {
		return nil, err
	}
	thumb := thumbnail(src, size)
	var buf bytes.Buffer
	hasAlpha := imageHasAlpha(thumb)
	var wimg *image.RGBA
	_ = wimg
	if hasAlpha {
		wimg = thumb.(*image.RGBA)
	} else {
		rgb := image.NewRGBA(thumb.Bounds())
		stddraw.Draw(rgb, thumb.Bounds(), thumb, thumb.Bounds().Min, stddraw.Src)
		wimg = rgb
	}
	opts, err := encoder.NewLossyEncoderOptions(encoder.PresetDefault, 82)
	if err != nil {
		return nil, err
	}
	if err := webp.Encode(&buf, wimg, opts); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// thumbnail 保持比例缩放到不超过 size×size。
func thumbnail(src image.Image, size int) image.Image {
	bounds := src.Bounds()
	w, h := bounds.Dx(), bounds.Dy()
	if w <= size && h <= size {
		return src
	}
	ratio := float64(size) / float64(maxInt(w, h))
	nw := int(float64(w) * ratio)
	nh := int(float64(h) * ratio)
	if nw < 1 {
		nw = 1
	}
	if nh < 1 {
		nh = 1
	}
	dst := image.NewRGBA(image.Rect(0, 0, nw, nh))
	xdraw.CatmullRom.Scale(dst, dst.Bounds(), src, bounds, xdraw.Over, nil)
	return dst
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// IsFileReferenced 判断图片是否被业务引用。
func IsFileReferenced(db *gorm.DB, fileID string) (bool, error) {
	var count int64
	for _, model := range []any{
		&models.StockMaterialImage{}, &models.PurchaseMaterialImage{},
		&models.PurchaseRequestLineImage{},
	} {
		if err := db.Model(model).Where("file_id = ?", fileID).Count(&count).Error; err != nil {
			return false, err
		}
		if count > 0 {
			return true, nil
		}
	}
	return false, nil
}

// DeleteImage 删除图片（被引用则 409 FILE_IN_USE）。
func DeleteImage(cfg *config.Config, db *gorm.DB, fileID string) *apperrors.AppError {
	item, _, appErr := GetImage(cfg, db, fileID)
	if appErr != nil {
		return appErr
	}
	referenced, err := IsFileReferenced(db, fileID)
	if err != nil {
		return DatabaseError(err)
	}
	if referenced {
		return apperrors.New("FILE_IN_USE", "图片已被业务引用，不能删除", 409, nil)
	}
	if err := db.Delete(&models.FileObject{}, "id = ?", item.ID).Error; err != nil {
		return DatabaseError(err)
	}
	_ = os.Remove(filePath(cfg, fileID))
	return nil
}

// OrphanFileRecord 孤儿记录。
type OrphanFileRecord struct {
	ID           string
	OriginalName string
	SizeBytes    int64
	CreatedAt    time.Time
	FileExists   bool
}

// InspectOrphans 孤儿报告：未被引用且早于 cutoff 的记录 + 磁盘上无记录的 .png。
func InspectOrphans(cfg *config.Config, db *gorm.DB, olderThanHours int) (cutoff time.Time, unreferenced []OrphanFileRecord, untracked, missing []string, appErr *apperrors.AppError) {
	cutoff = models.UTCNow().Add(-time.Duration(olderThanHours) * time.Hour)

	var all []models.FileObject
	if err := db.Order("created_at, id").Find(&all).Error; err != nil {
		return time.Time{}, nil, nil, nil, DatabaseError(err)
	}
	unreferenced = []OrphanFileRecord{}
	for i := range all {
		item := &all[i]
		if item.CreatedAt.After(cutoff) {
			continue
		}
		referenced, err := IsFileReferenced(db, item.ID)
		if err != nil {
			return time.Time{}, nil, nil, nil, DatabaseError(err)
		}
		if referenced {
			continue
		}
		path := filePath(cfg, item.ID)
		_, statErr := os.Stat(path)
		unreferenced = append(unreferenced, OrphanFileRecord{
			ID:           item.ID,
			OriginalName: item.OriginalName,
			SizeBytes:    item.SizeBytes,
			CreatedAt:    item.CreatedAt,
			FileExists:   statErr == nil,
		})
	}

	diskFiles := managedDiskFiles(cfg)
	recordIDs := map[string]bool{}
	for _, item := range all {
		recordIDs[item.ID] = true
	}
	cutoffUnix := cutoff.Unix()
	untracked = []string{}
	for name, path := range diskFiles {
		if recordIDs[strings.TrimSuffix(name, ".png")] {
			continue
		}
		if info, err := os.Stat(path); err == nil && info.ModTime().Unix() <= cutoffUnix {
			untracked = append(untracked, name)
		}
	}
	sort.Strings(untracked)

	missing = []string{}
	for _, item := range all {
		if item.CreatedAt.After(cutoff) {
			continue
		}
		if _, ok := diskFiles[item.ID+".png"]; !ok {
			missing = append(missing, item.ID)
		}
	}
	sort.Strings(missing)
	return cutoff, unreferenced, untracked, missing, nil
}

func managedDiskFiles(cfg *config.Config) map[string]string {
	_ = os.MkdirAll(cfg.UploadDirPath, 0o755)
	out := map[string]string{}
	entries, err := os.ReadDir(cfg.UploadDirPath)
	if err != nil {
		return out
	}
	for _, e := range entries {
		if e.IsDir() || !managedFileName.MatchString(e.Name()) {
			continue
		}
		out[e.Name()] = filepath.Join(cfg.UploadDirPath, e.Name())
	}
	return out
}

// CleanupOrphans 清理孤儿记录与磁盘文件。
func CleanupOrphans(cfg *config.Config, db *gorm.DB, olderThanHours int) (cutoff time.Time, deletedRecordIDs, deletedFileNames []string, appErr *apperrors.AppError) {
	cutoff, unreferenced, untracked, _, appErr := InspectOrphans(cfg, db, olderThanHours)
	if appErr != nil {
		return time.Time{}, nil, nil, appErr
	}
	deletedRecordIDs = []string{}
	for _, rec := range unreferenced {
		referenced, err := IsFileReferenced(db, rec.ID)
		if err != nil {
			return time.Time{}, nil, nil, DatabaseError(err)
		}
		if referenced {
			continue
		}
		if err := db.Delete(&models.FileObject{}, "id = ?", rec.ID).Error; err != nil {
			return time.Time{}, nil, nil, DatabaseError(err)
		}
		deletedRecordIDs = append(deletedRecordIDs, rec.ID)
	}
	deletedFileNames = []string{}
	candidates := map[string]bool{}
	for _, id := range deletedRecordIDs {
		candidates[id+".png"] = true
	}
	for _, name := range untracked {
		candidates[name] = true
	}
	names := make([]string, 0, len(candidates))
	for name := range candidates {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		path := filepath.Join(cfg.UploadDirPath, name)
		if _, err := os.Stat(path); err == nil {
			if err := os.Remove(path); err == nil {
				deletedFileNames = append(deletedFileNames, name)
			}
		}
	}
	return cutoff, deletedRecordIDs, deletedFileNames, nil
}
