package handler

import (
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// CodesHandler 物料编码库 / 华星库存 / 精简二级库 + 导入。
type CodesHandler struct {
	App *App
}

func NewCodesHandler(app *App) *CodesHandler { return &CodesHandler{App: app} }

// ============ 物料编码库 ============

// MaterialCodes GET /material-code-library
func (h *CodesHandler) MaterialCodes(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.SearchMaterialCodes(h.App.DB, c.Query("keyword"),
		c.Query("name"), c.Query("model_spec"), c.Query("material_code"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.MaterialCodeLibraryRead, 0, len(items))
	for i := range items {
		reads = append(reads, dto.MaterialCodeLibraryRead{
			ID: items[i].ID, MaterialCode: items[i].MaterialCode,
			Name: items[i].Name, ModelSpec: items[i].ModelSpec, UnitName: items[i].UnitName,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.MaterialCodeLibraryRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// MaterialCodeExists GET /material-code-library/exists
func (h *CodesHandler) MaterialCodeExists(c *gin.Context) {
	code := c.Query("material_code")
	respond.JSON(c, http.StatusOK, dto.MaterialCodeExistsRead{
		MaterialCode: code, Exists: service.MaterialCodeExists(h.App.DB, code),
	})
}

// ============ 华星库存 ============

// HuaXing GET /huaxing-inventory
func (h *CodesHandler) HuaXing(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.SearchHuaXingInventory(h.App.DB, c.Query("keyword"),
		c.Query("material_code"), c.Query("name"), c.Query("model_spec"),
		c.Query("purchase_department"), c.Query("purchaser"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.HuaXingInventoryRead, 0, len(items))
	for i := range items {
		item := &items[i]
		var qty *string
		if item.Quantity != nil {
			s := serialize.DecimalToString(item.Quantity.Decimal)
			qty = &s
		}
		reads = append(reads, dto.HuaXingInventoryRead{
			ID: item.ID, FirstInboundDate: datePtr(item.FirstInboundDate),
			Warehouse: item.Warehouse, MaterialCode: item.MaterialCode, Name: item.Name,
			ModelSpec: item.ModelSpec, Quantity: qty, UnitName: item.UnitName,
			Purchaser: item.Purchaser, PurchaseDepartment: item.PurchaseDepartment,
			SubitemNoName: item.SubitemNoName,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.HuaXingInventoryRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// HuaXingFilterOptions GET /huaxing-inventory/filter-options
func (h *CodesHandler) HuaXingFilterOptions(c *gin.Context) {
	departments, purchasers, appErr := service.HuaXingFilterOptions(h.App.DB)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.HuaXingFilterOptions{
		PurchaseDepartments: departments, Purchasers: purchasers,
	})
}

// ============ 精简二级库 ============

// LiteInventory GET /secondary-warehouse
func (h *CodesHandler) LiteInventory(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.SearchLiteInventory(h.App.DB, c.Query("name"), c.Query("model_spec"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.LiteInventoryRead, 0, len(items))
	for i := range items {
		item := &items[i]
		var qty *string
		if item.Quantity != nil {
			s := serialize.DecimalToString(item.Quantity.Decimal)
			qty = &s
		}
		reads = append(reads, dto.LiteInventoryRead{
			ID: item.ID, Name: item.Name, ModelSpec: item.ModelSpec,
			UnitName: item.UnitName, Quantity: qty, Remark: item.Remark,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.LiteInventoryRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// ============ 导入（通用） ============

var supportedImportSuffixes = []string{".xlsx", ".xlsm", ".xls", ".csv"}

func supportedSuffix(filename string) bool {
	lower := strings.ToLower(filename)
	for _, suffix := range supportedImportSuffixes {
		if strings.HasSuffix(lower, suffix) {
			return true
		}
	}
	return false
}

// Import POST /{prefix}/import
func (h *CodesHandler) Import(c *gin.Context) {
	importType, _ := c.Get("import_type")
	importTypeStr, _ := importType.(string)
	fileHeader, err := c.FormFile("file")
	if err != nil {
		respond.Error(c, appErrNew("VALIDATION_ERROR", "缺少上传文件", 422, nil))
		return
	}
	filename := fileHeader.Filename
	if !supportedSuffix(filename) {
		respond.Error(c, appErrNew("UNSUPPORTED_EXCEL_FILE", "仅支持 .xls、.xlsx 或 .csv 格式的表格文件", 0, nil))
		return
	}
	f, err := fileHeader.Open()
	if err != nil {
		respond.Error(c, appErrNew("INVALID_EXCEL_FILE", "无法读取上传文件", 0, nil))
		return
	}
	defer f.Close()
	filePath, appErr := service.SaveImportUpload(h.App.Cfg, filename, f)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	user := auth.CurrentUser(c)
	var createdBy *int64
	if user != nil {
		createdBy = &user.ID
	}
	var processor service.ImportProcessor
	switch importType {
	case "MATERIAL_CODE_LIBRARY":
		processor = service.ProcessMaterialCodeImport
	case "HUAXING_INVENTORY":
		processor = service.ProcessHuaXingImport
	case "LITE_INVENTORY":
		processor = service.ProcessLiteImport
	default:
		respond.Error(c, appErrNew("VALIDATION_ERROR", "未知导入类型", 422, nil))
		return
	}
	job, appErr := service.EnqueueImport(h.App.DB, importTypeStr, filename, filePath, createdBy, processor)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusAccepted, importJobRead(job))
}

// ImportJob GET /{prefix}/import-jobs/{job_id}
func (h *CodesHandler) ImportJob(c *gin.Context) {
	importType, _ := c.Get("import_type")
	importTypeStr, _ := importType.(string)
	jobID, ok := parseIDParam(c, "job_id")
	if !ok {
		return
	}
	job, appErr := service.GetImportJob(h.App.DB, importTypeStr, jobID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, importJobRead(job))
}

// LastImport GET /{prefix}/last-import
func (h *CodesHandler) LastImport(c *gin.Context) {
	importType, _ := c.Get("import_type")
	importTypeStr, _ := importType.(string)
	lastAt := service.LatestImportFinishedAt(h.App.DB, importTypeStr)
	var last *serialize.OffsetTime
	if lastAt != nil {
		t := serialize.OffsetTime(*lastAt)
		last = &t
	}
	respond.JSON(c, http.StatusOK, dto.LastImportRead{LastImportAt: last})
}

func importJobRead(job *modelsExcelImportJob) *dto.ExcelImportJobRead {
	var result map[string]any
	_ = service.DecodeJSON(job.Result, &result)
	read := &dto.ExcelImportJobRead{
		ID: job.ID, ImportType: job.ImportType, Status: job.Status,
		OriginalFilename: job.OriginalFilename, Result: result,
		ErrorCode: job.ErrorCode, ErrorMessage: job.ErrorMessage,
		CreatedAt: serialize.OffsetTime(job.CreatedAt),
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

func setType(importType string) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Set("import_type", importType)
		c.Next()
	}
}

// RegisterCodes 注册编码库/华星/二级库路由。
func RegisterCodes(r *gin.RouterGroup, app *App) {
	h := NewCodesHandler(app)
	authM := auth.AuthManagement(app.Cfg, app.DB)
	writer := auth.WarehouseWriter()

	codeGroup := r.Group("/material-code-library", authM)
	codeGroup.GET("", h.MaterialCodes)
	codeGroup.GET("/exists", h.MaterialCodeExists)
	codeGroup.GET("/last-import", setType("MATERIAL_CODE_LIBRARY"), h.LastImport)
	codeGroup.GET("/import-jobs/:job_id", setType("MATERIAL_CODE_LIBRARY"), h.ImportJob)
	codeGroup.POST("/import", writer, setType("MATERIAL_CODE_LIBRARY"), h.Import)

	huaGroup := r.Group("/huaxing-inventory", authM)
	huaGroup.GET("", h.HuaXing)
	huaGroup.GET("/filter-options", h.HuaXingFilterOptions)
	huaGroup.GET("/last-import", setType("HUAXING_INVENTORY"), h.LastImport)
	huaGroup.GET("/import-jobs/:job_id", setType("HUAXING_INVENTORY"), h.ImportJob)
	huaGroup.POST("/import", writer, setType("HUAXING_INVENTORY"), h.Import)

	liteGroup := r.Group("/secondary-warehouse", authM)
	liteGroup.GET("", h.LiteInventory)
	liteGroup.GET("/last-import", setType("LITE_INVENTORY"), h.LastImport)
	liteGroup.GET("/import-jobs/:job_id", setType("LITE_INVENTORY"), h.ImportJob)
	liteGroup.POST("/import", writer, setType("LITE_INVENTORY"), h.Import)
}
