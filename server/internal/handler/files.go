package handler

import (
	"io"
	"net/http"
	"regexp"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

const filesCacheControl = "public, max-age=86400, s-maxage=2592000"

var fileIDPattern = regexp.MustCompile(
	`^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)

// FilesHandler 图片附件。
type FilesHandler struct {
	App *App
}

func NewFilesHandler(app *App) *FilesHandler { return &FilesHandler{App: app} }

// Upload POST /files/images（FileWriter）
func (h *FilesHandler) Upload(c *gin.Context) {
	fileHeader, err := c.FormFile("file")
	if err != nil {
		respond.Error(c, apperrors.New("VALIDATION_ERROR", "缺少上传文件", 422, nil))
		return
	}
	contentType := fileHeader.Header.Get("Content-Type")
	if contentType == "" {
		// 未带 Content-Type 时按扩展名推断
		contentType = sniffContentType(fileHeader.Filename)
	}
	f, err := fileHeader.Open()
	if err != nil {
		respond.Error(c, apperrors.New("INVALID_IMAGE", "图片无法读取", 0, nil))
		return
	}
	defer f.Close()
	raw, err := io.ReadAll(io.LimitReader(f, h.App.Cfg.MaxImageBytes+1))
	if err != nil {
		respond.Error(c, apperrors.New("INVALID_IMAGE", "图片无法读取", 0, nil))
		return
	}
	item, appErr := service.SaveImage(h.App.Cfg, h.App.DB, contentType, fileHeader.Filename, raw)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusCreated, dto.NewFileObjectRead(item))
}

func sniffContentType(filename string) string {
	switch {
	case regexp.MustCompile(`(?i)\.png$`).MatchString(filename):
		return "image/png"
	case regexp.MustCompile(`(?i)\.jpe?g$`).MatchString(filename):
		return "image/jpeg"
	case regexp.MustCompile(`(?i)\.webp$`).MatchString(filename):
		return "image/webp"
	}
	return "application/octet-stream"
}

// ReadImage GET /files/images/{file_id}?size=（匿名）
func (h *FilesHandler) ReadImage(c *gin.Context) {
	fileID := c.Param("file_id")
	if !fileIDPattern.MatchString(fileID) {
		respond.Error(c, apperrors.New("VALIDATION_ERROR", "无效的图片 ID", 422, nil))
		return
	}
	item, path, appErr := service.GetImage(h.App.Cfg, h.App.DB, fileID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	sizeRaw := c.Query("size")
	if sizeRaw != "" {
		size, err := strconv.Atoi(sizeRaw)
		if err != nil || size < 16 || size > 2048 {
			respond.Error(c, apperrors.New("VALIDATION_ERROR", "size 必须是 16-2048 的整数", 422, nil))
			return
		}
		preview, err := service.RenderPreview(path, size)
		if err != nil {
			respond.Error(c, apperrors.New("INVALID_IMAGE", "图片无法生成预览", 0, nil))
			return
		}
		c.Header("Cache-Control", filesCacheControl)
		c.Data(http.StatusOK, "image/webp", preview)
		return
	}
	c.Header("Cache-Control", filesCacheControl)
	c.Header("Content-Disposition", `inline; filename="`+item.ID+`.png"`)
	c.File(path)
}

// OrphanReport GET /files/images/orphans（SuperAdmin）
func (h *FilesHandler) OrphanReport(c *gin.Context) {
	olderThan, appErr := binding.QueryInt(c, "older_than_hours", 24, 0, 87600)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	cutoff, unreferenced, untracked, missing, appErr := service.InspectOrphans(h.App.Cfg, h.App.DB, olderThan)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	records := make([]dto.OrphanFileRead, 0, len(unreferenced))
	for _, rec := range unreferenced {
		records = append(records, dto.OrphanFileRead{
			ID:           rec.ID,
			OriginalName: rec.OriginalName,
			SizeBytes:    rec.SizeBytes,
			CreatedAt:    serialize.UTCZTime(rec.CreatedAt),
			FileExists:   rec.FileExists,
		})
	}
	if untracked == nil {
		untracked = []string{}
	}
	if missing == nil {
		missing = []string{}
	}
	respond.JSON(c, http.StatusOK, dto.OrphanFileReportRead{
		Cutoff:              serialize.UTCZTime(cutoff),
		UnreferencedRecords: records,
		UntrackedFileNames:  untracked,
		MissingFileIDs:      missing,
	})
}

// OrphanCleanup DELETE /files/images/orphans（SuperAdmin）
func (h *FilesHandler) OrphanCleanup(c *gin.Context) {
	olderThan, appErr := binding.QueryInt(c, "older_than_hours", 24, 0, 87600)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	cutoff, deletedRecordIDs, deletedFileNames, appErr := service.CleanupOrphans(h.App.Cfg, h.App.DB, olderThan)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if deletedRecordIDs == nil {
		deletedRecordIDs = []string{}
	}
	if deletedFileNames == nil {
		deletedFileNames = []string{}
	}
	respond.JSON(c, http.StatusOK, dto.OrphanFileCleanupRead{
		Cutoff:           serialize.UTCZTime(cutoff),
		DeletedRecordIDs: deletedRecordIDs,
		DeletedFileNames: deletedFileNames,
	})
}

// Delete DELETE /files/images/{file_id}（FileWriter）
func (h *FilesHandler) Delete(c *gin.Context) {
	fileID := c.Param("file_id")
	if !fileIDPattern.MatchString(fileID) {
		respond.Error(c, apperrors.New("VALIDATION_ERROR", "无效的图片 ID", 422, nil))
		return
	}
	if appErr := service.DeleteImage(h.App.Cfg, h.App.DB, fileID); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	c.Status(http.StatusNoContent)
}

// RegisterFiles 注册 /files/images 路由。
func RegisterFiles(r *gin.RouterGroup, app *App) {
	h := NewFilesHandler(app)
	group := r.Group("/files/images")
	// 匿名读取
	group.GET("/:file_id", h.ReadImage)
	// 管理端
	authGroup := group.Group("", auth.AuthManagement(app.Cfg, app.DB))
	fileWriter := auth.RequireRoles("SUPER_ADMIN", "WAREHOUSE_ADMIN", "PURCHASE_ADMIN")
	authGroup.POST("", fileWriter, h.Upload)
	authGroup.DELETE("/:file_id", fileWriter, h.Delete)
	authGroup.GET("/orphans", auth.SuperAdmin(), h.OrphanReport)
	authGroup.DELETE("/orphans", auth.SuperAdmin(), h.OrphanCleanup)
}
