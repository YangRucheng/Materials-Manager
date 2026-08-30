package service

import (
	"os"
	"path/filepath"
	"strings"
	"time"

	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/domain"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

const exportRetentionDays = 3

// ExportProcessor 导出处理器：生成文件到 target 并返回结果摘要。
type ExportProcessor func(db *gorm.DB, target, paramsJSON string) (map[string]any, string, *apperrors.AppError)

// ExportsDir 导出文件目录。
func ExportsDir(cfg *config.Config) string {
	dir := filepath.Join(cfg.UploadDirPath, "exports")
	_ = os.MkdirAll(dir, 0o755)
	return dir
}

// NewExportTarget 新导出目标文件路径（uuid7.xlsx）。
func NewExportTarget(cfg *config.Config) string {
	return filepath.Join(ExportsDir(cfg), security.UUID7String()+".xlsx")
}

// EnqueueExport 登记导出任务并后台执行。
func EnqueueExport(cfg *config.Config, db *gorm.DB, exportType, paramsJSON string, createdBy *int64, processor ExportProcessor) (*models.ExcelExportJob, *apperrors.AppError) {
	job := models.ExcelExportJob{
		ExportType: exportType,
		Status:     domain.JobPending,
		Params:     models.JSON(paramsJSON),
		CreatedBy:  createdBy,
		CreatedAt:  models.UTCNow(),
		UpdatedAt:  models.UTCNow(),
	}
	if err := db.Create(&job).Error; err != nil {
		return nil, DatabaseError(err)
	}
	target := NewExportTarget(cfg)
	jobID := job.ID
	go runExportJob(cfg, db, jobID, target, exportType, paramsJSON, processor)
	return &job, nil
}

func runExportJob(cfg *config.Config, db *gorm.DB, jobID int64, target, exportType, paramsJSON string, processor ExportProcessor) {
	now := models.UTCNow()
	db.Model(&models.ExcelExportJob{}).Where("id = ?", jobID).
		Updates(map[string]any{"status": domain.JobRunning, "started_at": now, "updated_at": now})

	result, filename, appErr := processor(db, target, paramsJSON)
	finishedAt := models.UTCNow()
	if appErr != nil {
		db.Model(&models.ExcelExportJob{}).Where("id = ?", jobID).
			Updates(map[string]any{
				"status":        domain.JobFailed,
				"error_code":    appErr.Code,
				"error_message": Truncate(appErr.Message, 1000),
				"finished_at":   finishedAt,
				"updated_at":    finishedAt,
			})
		_ = os.Remove(target)
		return
	}
	if filename != "" {
		// 文件以 uuid7.xlsx 落盘，download_filename 另存
		_ = os.WriteFile(filepath.Join(cfg.UploadDirPath, "exports", "meta-"+filepath.Base(target)), []byte(filename), 0o644)
	}
	db.Model(&models.ExcelExportJob{}).Where("id = ?", jobID).
		Updates(map[string]any{
			"status":            domain.JobSucceeded,
			"download_filename": filename,
			"file_path":         target,
			"result":            mustJSON(result),
			"finished_at":       finishedAt,
			"updated_at":        finishedAt,
		})
}

// GetExportJob 查询导出任务。
func GetExportJob(db *gorm.DB, jobID int64) (*models.ExcelExportJob, *apperrors.AppError) {
	var job models.ExcelExportJob
	err := db.First(&job, jobID).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("导出任务")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	return &job, nil
}

// GetExportFileByUUID 匿名下载导出文件。
func GetExportFileByUUID(cfg *config.Config, db *gorm.DB, fileUUID string) (string, string, *apperrors.AppError) {
	target := filepath.Join(ExportsDir(cfg), fileUUID+".xlsx")
	if _, err := os.Stat(target); os.IsNotExist(err) {
		return "", "", apperrors.New("EXPORT_FILE_NOT_FOUND", "导出文件不存在或已过期", 400, nil)
	}
	downloadName := fileUUID + ".xlsx"
	var job models.ExcelExportJob
	if err := db.Where("file_path = ?", target).First(&job).Error; err == nil && job.DownloadFilename != nil {
		downloadName = *job.DownloadFilename
	}
	return target, downloadName, nil
}

// MarkStaleExportsFailed 启动清理。
func MarkStaleExportsFailed(cfg *config.Config, db *gorm.DB) int {
	var jobs []models.ExcelExportJob
	db.Where("status IN ?", []string{domain.JobPending, domain.JobRunning}).Find(&jobs)
	if len(jobs) == 0 {
		return 0
	}
	now := models.UTCNow()
	db.Model(&models.ExcelExportJob{}).
		Where("status IN ?", []string{domain.JobPending, domain.JobRunning}).
		Updates(map[string]any{
			"status": domain.JobFailed, "error_code": "SERVER_RESTARTED",
			"error_message": "服务重启，导出任务已中断", "finished_at": now, "updated_at": now,
		})
	for _, job := range jobs {
		if job.FilePath != nil {
			_ = os.Remove(*job.FilePath)
		}
	}
	return len(jobs)
}

// CleanupFinishedExports 清理过期导出（3 天）与 .tmp 孤儿。
// 任务行与文件同生共死：删除行即删除对应 xlsx（对齐 Python 清理 worker）。
func CleanupFinishedExports(cfg *config.Config, db *gorm.DB) int {
	cutoff := models.UTCNow().Add(-time.Duration(exportRetentionDays) * 24 * time.Hour)
	// 先收集过期任务的 file_path，再删除行
	var expired []models.ExcelExportJob
	if err := db.Where("status IN ? AND finished_at < ?",
		[]string{domain.JobSucceeded, domain.JobFailed}, cutoff).Find(&expired).Error; err != nil {
		return 0
	}
	if len(expired) == 0 {
		return 0
	}
	ids := make([]int64, 0, len(expired))
	for _, job := range expired {
		ids = append(ids, job.ID)
	}
	if err := db.Where("id IN ?", ids).Delete(&models.ExcelExportJob{}).Error; err != nil {
		return 0
	}
	// 删除对应导出文件（失败静默：文件缺失/权限问题不阻断）
	for _, job := range expired {
		if job.FilePath != nil {
			_ = os.Remove(*job.FilePath)
		}
	}
	// 清扫 24h 前的 .tmp 孤儿
	entries, _ := os.ReadDir(ExportsDir(cfg))
	for _, e := range entries {
		if strings.HasSuffix(e.Name(), ".tmp") {
			info, err := e.Info()
			if err == nil && info.ModTime().Before(models.UTCNow().Add(-24*time.Hour)) {
				_ = os.Remove(filepath.Join(ExportsDir(cfg), e.Name()))
			}
		}
	}
	return len(expired)
}
