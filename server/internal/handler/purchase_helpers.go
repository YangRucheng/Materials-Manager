package handler

import (
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"path/filepath"

	"github.com/yangrucheng/materials-manager/server/internal/config"

	"github.com/yangrucheng/materials-manager/server/internal/dto"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// 类型别名，便于复用既有 handler 风格。
type gormDB = gorm.DB
type modelsPurchaseMaterial = models.PurchaseMaterial
type modelsPurchaseRequestLine = models.PurchaseRequestLine
type modelsPurchasePlanTemplate = models.PurchasePlanTemplate
type modelsShareLink = models.ShareLink
type modelsExcelImportJob = models.ExcelImportJob
type modelsExcelExportJob = models.ExcelExportJob
type appErr = apperrors.AppError

func appErrNew(code, msg string, status int, details map[string]any) *appErr {
	return apperrors.New(code, msg, status, details)
}

func derefStr(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func parseOptionalBool(c *gin.Context, name string) *bool {
	v := c.Query(name)
	if v == "" {
		return nil
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		return nil
	}
	return &b
}

func parseBool(c *gin.Context, name string) bool {
	v := c.Query(name)
	if v == "" {
		return false
	}
	b, _ := strconv.ParseBool(v)
	return b
}

func contains(list []string, v string) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

func datePtr(t *time.Time) *serialize.Date {
	if t == nil {
		return nil
	}
	d := serialize.Date(*t)
	return &d
}

// recordRead 组装 PurchaseRecordRead。
func recordRead(db *gorm.DB, line *models.PurchaseRequestLine) *dto.PurchaseRecordRead {
	var request models.PurchaseRequest
	if line.Request != nil {
		request = *line.Request
	} else {
		_ = db.Where("id = ?", line.PurchaseRequestID).First(&request).Error
	}
	images, _ := service.LoadRecordImages(db, line.ID)
	fileReads := make([]dto.FileObjectRead, 0, len(images))
	for i := range images {
		fileReads = append(fileReads, dto.NewFileObjectRead(&images[i]))
	}
	updatedAt := request.UpdatedAt
	if line.UpdatedAt.After(updatedAt) {
		updatedAt = line.UpdatedAt
	}
	return &dto.PurchaseRecordRead{
		LineID: line.ID, PurchaseRequestID: line.PurchaseRequestID,
		PurchaseMaterialID: line.PurchaseMaterialID, PlanNo: line.PlanNoSnapshot,
		PlanDate:        serialize.Date(line.PlanDateSnapshot),
		PurchaseOrderNo: request.PurchaseOrderNo, TraceNo: line.TraceNo,
		ContractNo: request.ContractNo, VesselNo: request.VesselNo,
		ConsolidationDate: datePtr(request.ConsolidationDate),
		ConsolidationPort: request.ConsolidationPort, SailingDate: datePtr(request.SailingDate),
		Status: line.Status, MaterialCode: line.MaterialCodeSnapshot, Category: line.CategorySnapshot,
		DemandDepartment: line.DemandDepartmentSnapshot, MaterialName: line.MaterialNameSnapshot,
		ModelSpec: line.ModelSpecSnapshot, UnitName: line.UnitNameSnapshot,
		PurchaseQty:         serialize.DecimalToString(line.PurchaseQty.Decimal),
		ActualDemandPerson:  line.ActualDemandPersonSnapshot,
		PurchaseResponsible: line.PurchaseResponsibleSnapshot,
		Salesperson:         line.Salesperson, PlanRemark: line.PlanRemarkSnapshot,
		RecordRemark: request.Remark, Usage: line.Usage, SubitemNo: line.SubitemNo,
		Images: fileReads, StockMaterialID: line.StockMaterialIDSnapshot,
		PurchaseDate: datePtr(request.PurchaseDate),
		CreatedAt:    serialize.UTCZTime(request.CreatedAt), UpdatedAt: serialize.UTCZTime(updatedAt),
		Version: request.Version,
	}
}

type configCfg = config.Config

func filePathOf(cfg *configCfg, fileID string) string {
	return filepath.Join(cfg.UploadDirPath, fileID+".png")
}

func strOf(data map[string]any, key string) string {
	if v, ok := data[key].(string); ok {
		return v
	}
	return ""
}

func boolOf(data map[string]any, key string) bool {
	if v, ok := data[key].(bool); ok {
		return v
	}
	return false
}

func boolPtr(v bool) *bool { return &v }

func statusNames(data map[string]any) []string {
	var out []string
	if list, ok := data["status"].([]any); ok {
		for _, item := range list {
			if s, ok := item.(string); ok {
				out = append(out, s)
			}
		}
	}
	return out
}
