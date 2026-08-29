package handler

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/shopspring/decimal"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/internal/excel"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

const exportRowLimit = 10000

// ExportJobsHandler 导出任务。
type ExportJobsHandler struct {
	App *App
}

func NewExportJobsHandler(app *App) *ExportJobsHandler { return &ExportJobsHandler{App: app} }

func exportJobRead(job *modelsExcelExportJob) *dto.ExcelExportJobRead {
	var result map[string]any
	_ = service.DecodeJSON(job.Result, &result)
	read := &dto.ExcelExportJobRead{
		ID: job.ID, ExportType: job.ExportType, Status: job.Status,
		DownloadFilename: job.DownloadFilename, Result: result,
		ErrorCode: job.ErrorCode, ErrorMessage: job.ErrorMessage,
		CreatedAt: serialize.OffsetTime(job.CreatedAt),
	}
	if job.FilePath != nil {
		base := filepath.Base(*job.FilePath)
		uuid := strings.TrimSuffix(base, ".xlsx")
		read.FileUUID = &uuid
	}
	if job.Params != nil && len(job.Params) > 0 {
		var params map[string]any
		_ = service.DecodeJSON(job.Params, &params)
		read.Params = params
	}
	if job.StartedAt != nil {
		t := serialize.OffsetTime(*job.StartedAt)
		read.StartedAt = &t
	}
	if job.FinishedAt != nil {
		t := serialize.OffsetTime(*job.FinishedAt)
		read.FinishedAt = &t
	}
	return read
}

// GetExportJob GET /excel-export-jobs/{job_id}
func (h *ExportJobsHandler) GetExportJob(c *gin.Context) {
	jobID, ok := parseIDParam(c, "job_id")
	if !ok {
		return
	}
	job, appErr := service.GetExportJob(h.App.DB, jobID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, exportJobRead(job))
}

// DownloadExportFile GET /excel-export-jobs/files/{file_uuid}（匿名）
func (h *ExportJobsHandler) DownloadExportFile(c *gin.Context) {
	fileUUID := c.Param("file_uuid")
	path, downloadName, appErr := service.GetExportFileByUUID(h.App.Cfg, h.App.DB, fileUUID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	c.Header("Content-Disposition", excel.ContentDisposition(downloadName))
	c.Header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	c.File(path)
}

// ============ 申购计划导出 ============

var planResultHeaders = map[string]string{
	"plan_no": "计划 ID", "plan_date": "需求日期", "material_code": "物料编码",
	"category": "类别", "urgency": "紧急程度", "demand_department": "需求部门",
	"name": "名称", "model_spec": "型号规格", "planned_qty": "计划数量",
	"unit_name": "计量单位", "actual_demand_person": "提报员工",
	"purchase_responsible": "实际需求人", "subitem_no": "子项号", "usage": "用途", "images": "图片",
}

// ExportPlanResults POST /purchase-materials/export-results（202）
func (h *ExportJobsHandler) ExportPlanResults(c *gin.Context) {
	var params map[string]any
	_ = json.NewDecoder(c.Request.Body).Decode(&params)
	user := auth.CurrentUser(c)
	var createdBy *int64
	if user != nil {
		createdBy = &user.ID
	}
	paramsJSON, _ := json.Marshal(params)
	processor := func(db *gormDB, target, paramsJSON string) (map[string]any, string, *appErr) {
		var data map[string]any
		_ = json.Unmarshal([]byte(paramsJSON), &data)
		items, total, appErr := service.SearchPurchaseMaterials(db,
			"", "", "", strOf(data, "name"), strOf(data, "model_spec"),
			strOf(data, "actual_demand_person"), boolOf(data, "empty_actual_demand_person"),
			"", strOf(data, "subitem_no"), boolOf(data, "empty_subitem_no"),
			strOf(data, "category"), statusNames(data), nil, boolPtr(false),
			1, exportRowLimit+1, strOf(data, "sort_by"), strOf(data, "sort_order"))
		if appErr != nil {
			return nil, "", appErr
		}
		if total > exportRowLimit {
			return nil, "", appErrNew("EXPORT_RESULT_LIMIT_EXCEEDED",
				"查询结果超过 10000 行，请缩小筛选范围后导出", 400,
				map[string]any{"total": total, "limit": exportRowLimit})
		}
		rows := buildPlanExportRows(h.App.Cfg, db, items)
		columns := columnsFromParams(data, planResultHeaders)
		content, filename, appErr := excel.RenderResultExcel("申购计划导出", columns, rows)
		if appErr != nil {
			return nil, "", appErr
		}
		if err := excel.WriteExportFile(target, content); err != nil {
			return nil, "", service.DatabaseError(err)
		}
		imageCount := 0
		for _, row := range rows {
			if imgs, ok := row["images"].([]string); ok {
				imageCount += len(imgs)
			}
		}
		return map[string]any{"download_filename": filename, "rows": len(rows), "image_count": imageCount}, filename, nil
	}
	job, appErr := service.EnqueueExport(h.App.Cfg, h.App.DB, "PURCHASE_PLAN_RESULTS", string(paramsJSON), createdBy, processor)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusAccepted, exportJobRead(job))
}

func buildPlanExportRows(cfg *configCfg, db *gormDB, items []modelsPurchaseMaterial) []map[string]any {
	rows := make([]map[string]any, 0, len(items))
	for i := range items {
		item := &items[i]
		var images []string
		var links []struct{ FileID string }
		_ = links
		var fileIDs []string
		db.Table("purchase_material_image").Where("material_id = ?", item.ID).Order("sort_order").Pluck("file_id", &fileIDs)
		for _, fid := range fileIDs {
			p := filePathOf(cfg, fid)
			if _, err := os.Stat(p); err == nil {
				images = append(images, p)
			}
		}
		rows = append(rows, map[string]any{
			"plan_no": item.PlanNo, "plan_date": serialize.FormatDate(item.PlanDate),
			"material_code": item.MaterialCode, "category": item.Category, "urgency": item.Urgency,
			"demand_department": item.DemandDepartment, "name": item.Name,
			"model_spec": item.ModelSpec, "planned_qty": serialize.DecimalToString(item.PlannedQty.Decimal),
			"unit_name": item.UnitName, "actual_demand_person": item.ActualDemandPerson,
			"purchase_responsible": item.PurchaseResponsible, "subitem_no": item.SubitemNo,
			"usage": item.Usage, "images": images,
		})
	}
	return rows
}

func columnsFromParams(data map[string]any, headers map[string]string) [][2]string {
	var keys []string
	if cols, ok := data["columns"].([]any); ok {
		for _, col := range cols {
			if s, ok := col.(string); ok {
				keys = append(keys, s)
			}
		}
	}
	out := make([][2]string, 0, len(keys))
	for _, key := range keys {
		if header, ok := headers[key]; ok {
			out = append(out, [2]string{key, header})
		}
	}
	return out
}

// ExportUncoded GET /purchase-materials/export-uncoded（同步模板导出）
func (h *ExportJobsHandler) ExportUncoded(c *gin.Context) {
	// 未编码 + 未转入 + 正常状态
	rows := service.UncodedMaterialRows(h.App.DB, c.Query("keyword"))
	content, filename, appErr := excel.RenderTemplate(h.App.Cfg.TemplateDir, "material-code-application.json", rows)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respondExcel(c, content, filename)
}

// ExportPurchaseApplication POST /purchase-materials/export-purchase-application
func (h *ExportJobsHandler) ExportPurchaseApplication(c *gin.Context) {
	var req struct {
		MaterialIDs []int64 `json:"material_ids"`
	}
	_ = json.NewDecoder(c.Request.Body).Decode(&req)
	rows, appErr := service.PurchaseApplicationRows(h.App.DB, req.MaterialIDs, "application")
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	content, filename, appErr := excel.RenderTemplate(h.App.Cfg.TemplateDir, "purchase-application.json", rows)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respondExcel(c, content, filename)
}

// ExportPurchaseApproval POST /purchase-materials/export-purchase-approval
func (h *ExportJobsHandler) ExportPurchaseApproval(c *gin.Context) {
	var req struct {
		MaterialIDs []int64 `json:"material_ids"`
	}
	_ = json.NewDecoder(c.Request.Body).Decode(&req)
	rows, appErr := service.PurchaseApplicationRows(h.App.DB, req.MaterialIDs, "approval")
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	content, filename, appErr := excel.RenderTemplate(h.App.Cfg.TemplateDir, "purchase-approval.json", rows)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respondExcel(c, content, filename)
}

func respondExcel(c *gin.Context, content []byte, filename string) {
	c.Header("Content-Disposition", excel.ContentDisposition(filename))
	c.Data(http.StatusOK, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content)
}

// RegisterExportJobs 注册导出路由。
func RegisterExportJobs(r *gin.RouterGroup, app *App) {
	h := NewExportJobsHandler(app)
	// 匿名下载
	r.GET("/excel-export-jobs/files/:file_uuid", h.DownloadExportFile)
	group := r.Group("/excel-export-jobs", auth.AuthManagement(app.Cfg, app.DB))
	group.GET("/:job_id", h.GetExportJob)

	pm := r.Group("/purchase-materials", auth.AuthManagement(app.Cfg, app.DB))
	pm.POST("/export-results", h.ExportPlanResults)
	pm.GET("/export-uncoded", h.ExportUncoded)
	pm.POST("/export-purchase-application", h.ExportPurchaseApplication)
	pm.POST("/export-purchase-approval", h.ExportPurchaseApproval)

	pr := r.Group("/purchase-records", auth.AuthManagement(app.Cfg, app.DB))
	pr.POST("/export-results", h.ExportRecordResults)
}

var recordResultHeaders = map[string]string{
	"purchase_qty": "申购数量", "plan_date": "需求日期", "purchase_order_no": "申购单号",
	"trace_no": "追溯号", "contract_no": "合同号", "vessel_no": "船号",
	"consolidation_date": "集港日期", "consolidation_port": "集港港口", "sailing_date": "发船日期",
	"category": "类别", "demand_department": "需求部门", "material_name": "物资名称",
	"model_spec": "物资型号", "material_code": "物料编码", "actual_demand_person": "提报员工",
	"usage": "用途", "purchase_responsible": "实际需求人", "salesperson": "业务员",
	"status": "状态", "purchase_date": "申购日期", "images": "图片", "subitem_no": "子项号",
}

// ExportRecordResults POST /purchase-records/export-results（202）
func (h *ExportJobsHandler) ExportRecordResults(c *gin.Context) {
	var params map[string]any
	_ = json.NewDecoder(c.Request.Body).Decode(&params)
	user := auth.CurrentUser(c)
	var createdBy *int64
	if user != nil {
		createdBy = &user.ID
	}
	paramsJSON, _ := json.Marshal(params)
	processor := func(db *gormDB, target, paramsJSON string) (map[string]any, string, *appErr) {
		var data map[string]any
		_ = json.Unmarshal([]byte(paramsJSON), &data)
		lines, total, appErr := service.SearchPurchaseRecords(db,
			strOf(data, "status"), boolOf(data, "empty_status"), "", "", "",
			strOf(data, "purchase_order_no"), strOf(data, "trace_no"), strOf(data, "category"),
			strOf(data, "name"), strOf(data, "model_spec"), strOf(data, "actual_demand_person"),
			strOf(data, "purchase_responsible"), strOf(data, "salesperson"),
			strOf(data, "subitem_no"), boolOf(data, "empty_subitem_no"),
			1, exportRowLimit+1, strOf(data, "sort_by"), strOf(data, "sort_order"))
		if appErr != nil {
			return nil, "", appErr
		}
		if total > exportRowLimit {
			return nil, "", appErrNew("EXPORT_RESULT_LIMIT_EXCEEDED",
				"查询结果超过 10000 行，请缩小筛选范围后导出", 400,
				map[string]any{"total": total, "limit": exportRowLimit})
		}
		rows := buildRecordExportRows(h.App.Cfg, db, lines)
		columns := columnsFromParams(data, recordResultHeaders)
		content, filename, appErr := excel.RenderResultExcel("申购记录导出", columns, rows)
		if appErr != nil {
			return nil, "", appErr
		}
		if err := excel.WriteExportFile(target, content); err != nil {
			return nil, "", service.DatabaseError(err)
		}
		imageCount := 0
		for _, row := range rows {
			if imgs, ok := row["images"].([]string); ok {
				imageCount += len(imgs)
			}
		}
		return map[string]any{"download_filename": filename, "rows": len(rows), "image_count": imageCount}, filename, nil
	}
	job, appErr := service.EnqueueExport(h.App.Cfg, h.App.DB, "PURCHASE_RECORD_RESULTS", string(paramsJSON), createdBy, processor)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusAccepted, exportJobRead(job))
}

func buildRecordExportRows(cfg *configCfg, db *gormDB, lines []modelsPurchaseRequestLine) []map[string]any {
	rows := make([]map[string]any, 0, len(lines))
	for i := range lines {
		line := &lines[i]
		read := recordRead(db, line)
		var images []string
		for _, img := range read.Images {
			p := filePathOf(cfg, img.ID)
			if _, err := os.Stat(p); err == nil {
				images = append(images, p)
			}
		}
		qtyText := serialize.DecimalToString(decFromQty(read.PurchaseQty)) + " " + read.UnitName
		rows = append(rows, map[string]any{
			"purchase_qty": qtyText, "plan_date": formatDateStr(read.PlanDate),
			"purchase_order_no": read.PurchaseOrderNo, "trace_no": read.TraceNo,
			"contract_no": read.ContractNo, "vessel_no": read.VesselNo,
			"consolidation_date": formatDatePtr(read.ConsolidationDate),
			"consolidation_port": read.ConsolidationPort, "sailing_date": formatDatePtr(read.SailingDate),
			"category": read.Category, "demand_department": read.DemandDepartment,
			"material_name": read.MaterialName, "model_spec": read.ModelSpec,
			"material_code": read.MaterialCode, "actual_demand_person": read.ActualDemandPerson,
			"usage": read.Usage, "purchase_responsible": read.PurchaseResponsible,
			"salesperson": read.Salesperson, "status": read.Status,
			"purchase_date": formatDatePtr(read.PurchaseDate), "subitem_no": read.SubitemNo,
			"images": images,
		})
	}
	return rows
}

func decFromQty(s string) decimal.Decimal {
	d, _ := decimal.NewFromString(s)
	return d
}

func formatDateStr(d serialize.Date) string {
	return serialize.FormatDate(time.Time(d))
}

func formatDatePtr(d *serialize.Date) *string {
	if d == nil {
		return nil
	}
	s := serialize.FormatDate(time.Time(*d))
	return &s
}
