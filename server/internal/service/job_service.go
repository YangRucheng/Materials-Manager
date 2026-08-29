package service

import (
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/domain"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

const (
	importDirName  = "imports"
	importChunk    = 1024 * 1024
	maxImportBytes = 50 * 1024 * 1024
)

// ImportProcessor 导入处理器（后台执行解析 + 全量替换）。
type ImportProcessor func(db *gorm.DB, filePath string) (map[string]any, *apperrors.AppError)

var typeLocks sync.Mutex
var typeLockMap = map[string]*sync.Mutex{}

func typeLock(importType string) *sync.Mutex {
	typeLocks.Lock()
	defer typeLocks.Unlock()
	lock, ok := typeLockMap[importType]
	if !ok {
		lock = &sync.Mutex{}
		typeLockMap[importType] = lock
	}
	return lock
}

// SaveImportUpload 流式保存上传文件到 imports 目录。
func SaveImportUpload(cfg *config.Config, filename string, reader io.Reader) (string, *apperrors.AppError) {
	base := filepath.Base(filename)
	suffix := strings.ToLower(filepath.Ext(base))
	if suffix == "" {
		suffix = ".xlsx"
	}
	importDir := filepath.Join(cfg.UploadDirPath, importDirName)
	if err := os.MkdirAll(importDir, 0o755); err != nil {
		return "", DatabaseError(err)
	}
	target := filepath.Join(importDir, security.UUID7String()+suffix)
	fh, err := os.Create(target)
	if err != nil {
		return "", DatabaseError(err)
	}
	total := int64(0)
	buf := make([]byte, importChunk)
	for {
		n, readErr := reader.Read(buf)
		if n > 0 {
			total += int64(n)
			if total > maxImportBytes {
				_ = fh.Close()
				_ = os.Remove(target)
				return "", apperrors.New("EXCEL_FILE_TOO_LARGE", "导入文件不能超过 50 MB", 0, nil)
			}
			if _, err := fh.Write(buf[:n]); err != nil {
				_ = fh.Close()
				_ = os.Remove(target)
				return "", DatabaseError(err)
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			_ = fh.Close()
			_ = os.Remove(target)
			return "", apperrors.New("INVALID_EXCEL_FILE", "无法读取上传文件", 0, nil)
		}
	}
	if err := fh.Close(); err != nil {
		_ = os.Remove(target)
		return "", DatabaseError(err)
	}
	return target, nil
}

// ImportJobItem 导入任务 read 组装所需信息。
type ImportJobItem struct {
	Job              *models.ExcelImportJob
	OriginalFilename string
}

func importJobStatusName(status string) string {
	return status
}

// EnqueueImport 登记 PENDING 任务并后台执行；同类进行中返回 409。
func EnqueueImport(db *gorm.DB, importType, originalFilename, filePath string, createdBy *int64, processor ImportProcessor) (*models.ExcelImportJob, *apperrors.AppError) {
	lock := typeLock(importType)
	lock.Lock()
	defer lock.Unlock()

	var activeID int64
	err := db.Model(&models.ExcelImportJob{}).
		Where("import_type = ? AND status IN ?", importType, []string{domain.JobPending, domain.JobRunning}).
		Order("id").Limit(1).Pluck("id", &activeID).Error
	if err != nil {
		return nil, DatabaseError(err)
	}
	if activeID != 0 {
		return nil, apperrors.New("IMPORT_IN_PROGRESS", "同类导入任务正在进行中，请稍后再试",
			http.StatusConflict, nil)
	}
	job := models.ExcelImportJob{
		ImportType:       importType,
		Status:           domain.JobPending,
		OriginalFilename: Truncate(originalFilename, 255),
		FilePath:         filePath,
		CreatedBy:        createdBy,
		CreatedAt:        models.UTCNow(),
		UpdatedAt:        models.UTCNow(),
	}
	if err := db.Create(&job).Error; err != nil {
		return nil, DatabaseError(err)
	}
	jobID := job.ID
	go runImportJob(db, jobID, filePath, processor)
	return &job, nil
}

func runImportJob(db *gorm.DB, jobID int64, filePath string, processor ImportProcessor) {
	now := models.UTCNow()
	db.Model(&models.ExcelImportJob{}).Where("id = ?", jobID).
		Updates(map[string]any{"status": domain.JobRunning, "started_at": now, "updated_at": now})

	result, appErr := processor(db, filePath)
	finishedAt := models.UTCNow()
	if appErr != nil {
		db.Model(&models.ExcelImportJob{}).Where("id = ?", jobID).
			Updates(map[string]any{
				"status":        domain.JobFailed,
				"error_code":    appErr.Code,
				"error_message": Truncate(appErr.Message, 1000),
				"finished_at":   finishedAt,
				"updated_at":    finishedAt,
			})
	} else {
		db.Model(&models.ExcelImportJob{}).Where("id = ?", jobID).
			Updates(map[string]any{
				"status":      domain.JobSucceeded,
				"result":      mustJSON(result),
				"finished_at": finishedAt,
				"updated_at":  finishedAt,
			})
	}
	_ = os.Remove(filePath)
}

// GetImportJob 查询导入任务（限定 import_type）。
func GetImportJob(db *gorm.DB, importType string, jobID int64) (*models.ExcelImportJob, *apperrors.AppError) {
	var job models.ExcelImportJob
	err := db.Where("id = ? AND import_type = ?", jobID, importType).First(&job).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("导入任务")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	return &job, nil
}

// LatestImportFinishedAt 该类型最近成功导入的完成时间。
func LatestImportFinishedAt(db *gorm.DB, importType string) *time.Time {
	var job models.ExcelImportJob
	err := db.Where("import_type = ? AND status = ?", importType, domain.JobSucceeded).
		Order("finished_at DESC").Limit(1).First(&job).Error
	if err != nil {
		return nil
	}
	return job.FinishedAt
}

// MarkStaleImportJobsFailed 启动清理：残留 PENDING/RUNNING 标记失败并删文件。
func MarkStaleImportJobsFailed(db *gorm.DB) int {
	var jobs []models.ExcelImportJob
	db.Where("status IN ?", []string{domain.JobPending, domain.JobRunning}).Find(&jobs)
	if len(jobs) == 0 {
		return 0
	}
	now := models.UTCNow()
	db.Model(&models.ExcelImportJob{}).
		Where("status IN ?", []string{domain.JobPending, domain.JobRunning}).
		Updates(map[string]any{
			"status":        domain.JobFailed,
			"error_code":    "SERVER_RESTARTED",
			"error_message": "服务重启，导入任务已中断",
			"finished_at":   now,
			"updated_at":    now,
		})
	for _, job := range jobs {
		_ = os.Remove(job.FilePath)
	}
	return len(jobs)
}

// CleanupFinishedImportJobs 清理 retention_days 前的终态任务行。
func CleanupFinishedImportJobs(db *gorm.DB, retentionDays int) int {
	cutoff := models.UTCNow().Add(-time.Duration(retentionDays) * 24 * time.Hour)
	res := db.Where("status IN ? AND finished_at < ?",
		[]string{domain.JobSucceeded, domain.JobFailed}, cutoff).Delete(&models.ExcelImportJob{})
	if res.Error != nil {
		return 0
	}
	return int(res.RowsAffected)
}
