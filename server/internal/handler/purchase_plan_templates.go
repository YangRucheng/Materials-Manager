package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// PurchasePlanTemplatesHandler 周期性计划模板。
type PurchasePlanTemplatesHandler struct {
	App *App
}

func NewPurchasePlanTemplatesHandler(app *App) *PurchasePlanTemplatesHandler {
	return &PurchasePlanTemplatesHandler{App: app}
}

func templateRead(db *gormDB, tpl *modelsPurchasePlanTemplate) *dto.PurchasePlanTemplateRead {
	var stockName *string
	if tpl.StockMaterialID != nil {
		var stock struct{ Name string }
		if db.Select("name").First(&stock, *tpl.StockMaterialID).Error == nil {
			stockName = &stock.Name
		}
	}
	var images []dto.FileObjectRead
	var linkIDs []string
	db.Table("purchase_plan_template_image").Where("plan_id = ?", tpl.ID).Order("sort_order").
		Pluck("file_id", &linkIDs)
	if len(linkIDs) > 0 {
		files, _ := service.LoadImagesByIDs(db, linkIDs)
		for i := range files {
			images = append(images, dto.NewFileObjectRead(&files[i]))
		}
	}
	return &dto.PurchasePlanTemplateRead{
		ID: tpl.ID, MaterialCode: tpl.MaterialCode, Category: tpl.Category,
		Urgency: tpl.Urgency, DemandDepartment: tpl.DemandDepartment, Name: tpl.Name,
		ModelSpec: tpl.ModelSpec, UnitName: tpl.UnitName,
		ActualDemandPerson: tpl.ActualDemandPerson, PurchaseResponsible: tpl.PurchaseResponsible,
		PlannedQty: serialize.DecimalToString(tpl.PlannedQty.Decimal),
		Usage:      tpl.Usage, SubitemNo: tpl.SubitemNo, Remark: tpl.Remark,
		StockMaterialID: tpl.StockMaterialID, StockMaterialName: stockName, Images: images,
		CreatedAt: serialize.UTCZTime(tpl.CreatedAt), UpdatedAt: serialize.UTCZTime(tpl.UpdatedAt),
		Version: tpl.Version,
	}
}

// List GET /purchase-plan-templates
func (h *PurchasePlanTemplatesHandler) List(c *gin.Context) {
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
	items, total, appErr := service.SearchTemplates(h.App.DB, c.Query("keyword"), c.Query("name"),
		c.Query("model_spec"), c.Query("actual_demand_person"), c.Query("purchase_responsible"),
		c.Query("category"), page, pageSize, c.Query("sort_by"), c.Query("sort_order"))
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.PurchasePlanTemplateRead, 0, len(items))
	for i := range items {
		reads = append(reads, *templateRead(h.App.DB, &items[i]))
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.PurchasePlanTemplateRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// FilterOptions GET /purchase-plan-templates/filter-options
func (h *PurchasePlanTemplatesHandler) FilterOptions(c *gin.Context) {
	persons, responsibles, categories, appErr := service.TemplateFilterOptions(h.App.DB)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.PurchasePlanTemplateFilterOptions{
		ActualDemandPersons: persons, PurchaseResponsibles: responsibles, Categories: categories,
	})
}

// Create POST /purchase-plan-templates
func (h *PurchasePlanTemplatesHandler) Create(c *gin.Context) {
	var req dto.PurchasePlanTemplateCreate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	tpl, appErr := service.CreateTemplate(h.App.DB, derefStr(req.MaterialCode), derefStr(req.Category),
		req.Urgency, req.DemandDepartment, req.Name, req.ModelSpec, req.UnitName,
		req.ActualDemandPerson, req.PurchaseResponsible, req.PlannedQty.Decimal, req.Usage,
		derefStr(req.SubitemNo), derefStr(req.Remark), req.StockMaterialID, req.ImageIDs)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusCreated, templateRead(h.App.DB, tpl))
}

// Detail GET /purchase-plan-templates/{template_id}
func (h *PurchasePlanTemplatesHandler) Detail(c *gin.Context) {
	templateID, ok := parseIDParam(c, "template_id")
	if !ok {
		return
	}
	tpl, appErr := service.LoadTemplateDetail(h.App.DB, templateID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, templateRead(h.App.DB, tpl))
}

// Update PATCH /purchase-plan-templates/{template_id}
func (h *PurchasePlanTemplatesHandler) Update(c *gin.Context) {
	templateID, ok := parseIDParam(c, "template_id")
	if !ok {
		return
	}
	var req dto.PurchasePlanTemplateUpdate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	tpl, appErr := service.LoadTemplateDetail(h.App.DB, templateID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	updated, appErr := service.UpdateTemplate(h.App.DB, tpl, derefStr(req.MaterialCode),
		derefStr(req.Category), req.Urgency, req.DemandDepartment, req.Name, req.ModelSpec,
		req.UnitName, req.ActualDemandPerson, req.PurchaseResponsible, req.PlannedQty.Decimal,
		req.Usage, derefStr(req.SubitemNo), derefStr(req.Remark), req.StockMaterialID,
		req.ImageIDs, req.Version)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, templateRead(h.App.DB, updated))
}

// Delete DELETE /purchase-plan-templates/{template_id}
func (h *PurchasePlanTemplatesHandler) Delete(c *gin.Context) {
	templateID, ok := parseIDParam(c, "template_id")
	if !ok {
		return
	}
	tpl, appErr := service.LoadTemplateDetail(h.App.DB, templateID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if appErr := service.DeleteTemplate(h.App.DB, tpl, parseIfMatch(c)); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	c.Status(http.StatusNoContent)
}

// Generate POST /purchase-plan-templates/{template_id}/generate
func (h *PurchasePlanTemplatesHandler) Generate(c *gin.Context) {
	templateID, ok := parseIDParam(c, "template_id")
	if !ok {
		return
	}
	tpl, appErr := service.LoadTemplateDetail(h.App.DB, templateID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	material, appErr := service.GeneratePurchasePlanFromTemplate(h.App.DB, tpl)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, purchaseRead(h.App.DB, material, nil))
}

// RegisterPurchasePlanTemplates 注册 /purchase-plan-templates 路由。
func RegisterPurchasePlanTemplates(r *gin.RouterGroup, app *App) {
	h := NewPurchasePlanTemplatesHandler(app)
	group := r.Group("/purchase-plan-templates", auth.AuthManagement(app.Cfg, app.DB))
	group.GET("", h.List)
	group.GET("/filter-options", h.FilterOptions)
	group.GET("/:template_id", h.Detail)
	write := group.Group("", auth.PurchaseWriter())
	write.POST("", h.Create)
	write.PATCH("/:template_id", h.Update)
	write.DELETE("/:template_id", h.Delete)
	write.POST("/:template_id/generate", h.Generate)
}
