package handler

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/domain"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// PurchaseMaterialsHandler 申购计划。
type PurchaseMaterialsHandler struct {
	App *App
}

func NewPurchaseMaterialsHandler(app *App) *PurchaseMaterialsHandler {
	return &PurchaseMaterialsHandler{App: app}
}

func purchaseRead(db *gormDB, item *modelsPurchaseMaterial, moved map[int64]bool) *dto.PurchaseMaterialRead {
	data, appErr := service.LoadPurchaseMaterialReadData(db, item, moved)
	if appErr != nil {
		return nil
	}
	images := make([]dto.FileObjectRead, 0, len(data.Images))
	for i := range data.Images {
		images = append(images, dto.NewFileObjectRead(&data.Images[i]))
	}
	return &dto.PurchaseMaterialRead{
		ID: item.ID, PlanNo: item.PlanNo, PlanDate: serialize.Date(item.PlanDate),
		MaterialCode: item.MaterialCode, Category: item.Category, Urgency: item.Urgency,
		DemandDepartment: item.DemandDepartment, Name: item.Name, ModelSpec: item.ModelSpec,
		UnitName: item.UnitName, ActualDemandPerson: item.ActualDemandPerson,
		PurchaseResponsible: item.PurchaseResponsible,
		PlannedQty:          serialize.DecimalToString(item.PlannedQty.Decimal),
		Usage:               item.Usage, SubitemNo: item.SubitemNo, Remark: item.Remark,
		StockMaterialID: item.StockMaterialID, StockMaterialName: data.StockMaterialName,
		Status: domain.PlanStatusValue[item.Status], MovedToRecord: data.MovedToRecord,
		Images: images, CreatedAt: serialize.UTCZTime(item.CreatedAt),
		UpdatedAt: serialize.UTCZTime(item.UpdatedAt), Version: item.Version,
	}
}

// List GET /purchase-materials
func (h *PurchaseMaterialsHandler) List(c *gin.Context) {
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
	user := auth.CurrentUser(c)
	isSuper := user != nil && user.Role == domain.RoleSuperAdmin
	var status []string
	for _, s := range c.QueryArray("status") {
		if name, ok := domain.PlanStatusName[s]; ok {
			status = append(status, name)
		}
	}
	if !isSuper {
		if contains(status, domain.PlanArchived) {
			respond.Error(c, archivedForbidden())
			return
		}
		if len(status) == 0 {
			status = []string{domain.PlanNormal}
		}
	}
	coded := parseOptionalBool(c, "coded")
	moved := parseOptionalBool(c, "moved")
	items, total, appErr := service.SearchPurchaseMaterials(h.App.DB, c.Query("keyword"),
		c.Query("search_field"), c.Query("search_value"), c.Query("name"), c.Query("model_spec"),
		c.Query("actual_demand_person"), parseBool(c, "empty_actual_demand_person"),
		c.Query("purchase_responsible"), c.Query("subitem_no"), parseBool(c, "empty_subitem_no"),
		c.Query("category"), status, coded, moved, page, pageSize,
		c.Query("sort_by"), c.Query("sort_order"))
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	ids := make([]int64, 0, len(items))
	for i := range items {
		ids = append(ids, items[i].ID)
	}
	movedMap, _ := service.PurchaseMaterialIDsMovedToRecord(h.App.DB, ids)
	reads := make([]dto.PurchaseMaterialRead, 0, len(items))
	for i := range items {
		reads = append(reads, *purchaseRead(h.App.DB, &items[i], movedMap))
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.PurchaseMaterialRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

func archivedForbidden() *appErr {
	return appErrNew("ARCHIVED_PURCHASE_PLAN_FORBIDDEN", "仅超级管理员可查询已归档申购计划", 403, nil)
}

// FilterOptions GET /purchase-materials/filter-options
func (h *PurchaseMaterialsHandler) FilterOptions(c *gin.Context) {
	user := auth.CurrentUser(c)
	isSuper := user != nil && user.Role == domain.RoleSuperAdmin
	var status []string
	if !isSuper {
		status = []string{domain.PlanNormal}
	}
	moved := parseOptionalBool(c, "moved")
	persons, responsibles, subitems, categories, appErr := service.PurchaseFilterOptions(h.App.DB, moved, status)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.PurchaseFilterOptions{
		ActualDemandPersons: persons, PurchaseResponsibles: responsibles,
		SubitemNos: subitems, Categories: categories,
	})
}

// Create POST /purchase-materials
func (h *PurchaseMaterialsHandler) Create(c *gin.Context) {
	var req dto.PurchaseMaterialCreate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	item, appErr := createPurchaseMaterial(h.App.DB, &req.PurchaseMaterialBase)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusCreated, purchaseRead(h.App.DB, item, nil))
}

func createPurchaseMaterial(db *gormDB, base *dto.PurchaseMaterialBase) (*modelsPurchaseMaterial, *appErr) {
	var planDate *time.Time
	if base.PlanDate != nil {
		if t, err := time.Parse("2006-01-02", *base.PlanDate); err == nil {
			planDate = &t
		}
	}
	status := domain.PlanNormal
	if base.Status != nil {
		status = domain.PlanStatusName[*base.Status]
	}
	return service.CreatePurchaseMaterialFull(db, planDate, derefStr(base.MaterialCode), derefStr(base.Category),
		base.Urgency, base.DemandDepartment, base.Name, base.ModelSpec, base.UnitName,
		base.ActualDemandPerson, base.PurchaseResponsible, base.PlannedQty.Decimal, base.Usage,
		derefStr(base.SubitemNo), derefStr(base.Remark), base.StockMaterialID, status, "", base.ImageIDs)
}

// Detail GET /purchase-materials/{material_id}
func (h *PurchaseMaterialsHandler) Detail(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	item, appErr := service.GetPurchaseMaterial(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	user := auth.CurrentUser(c)
	if item.Status == domain.PlanArchived && user != nil && user.Role != domain.RoleSuperAdmin {
		respond.Error(c, archivedForbidden())
		return
	}
	respond.JSON(c, http.StatusOK, purchaseRead(h.App.DB, item, nil))
}

// Update PATCH /purchase-materials/{material_id}
func (h *PurchaseMaterialsHandler) Update(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	var req dto.PurchaseMaterialUpdate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	item, appErr := service.GetPurchaseMaterial(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	var planDate *time.Time
	if req.PlanDate != nil {
		if t, err := time.Parse("2006-01-02", *req.PlanDate); err == nil {
			planDate = &t
		}
	}
	var statusPtr *string
	if req.Status != nil {
		s := domain.PlanStatusName[*req.Status]
		statusPtr = &s
	}
	updated, appErr := service.UpdatePurchaseMaterial(h.App.DB, item, planDate,
		derefStr(req.MaterialCode), derefStr(req.Category), req.Urgency, req.DemandDepartment,
		req.Name, req.ModelSpec, req.UnitName, req.ActualDemandPerson, req.PurchaseResponsible,
		req.PlannedQty.Decimal, req.Usage, derefStr(req.SubitemNo), derefStr(req.Remark),
		req.StockMaterialID, statusPtr, req.ImageIDs, req.Version)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, purchaseRead(h.App.DB, updated, nil))
}

// Delete DELETE /purchase-materials/{material_id}
func (h *PurchaseMaterialsHandler) Delete(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	item, appErr := service.GetPurchaseMaterial(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if appErr := service.DeletePurchaseMaterial(h.App.DB, item, parseIfMatch(c)); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	c.Status(http.StatusNoContent)
}

// LinkStockMaterial POST /purchase-materials/{material_id}/link-stock-material
func (h *PurchaseMaterialsHandler) LinkStockMaterial(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	var req dto.LinkStockMaterialRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	item, appErr := service.GetPurchaseMaterial(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	updated, appErr := service.LinkStockMaterial(h.App.DB, item, req.StockMaterialID, req.Version)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, purchaseRead(h.App.DB, updated, nil))
}

// MoveToRecord POST /purchase-materials/{material_id}/move-to-record
func (h *PurchaseMaterialsHandler) MoveToRecord(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	var req dto.MovePurchasePlanRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	lines, appErr := service.MovePlansToRecord(h.App.DB, []int64{materialID}, nil, "", "", "", "", "", "已申购", "", nil, nil, nil)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, recordRead(h.App.DB, &lines[0]))
}

// BatchMoveToRecord POST /purchase-materials/batch-move-to-record
func (h *PurchaseMaterialsHandler) BatchMoveToRecord(c *gin.Context) {
	var req dto.BatchMovePurchasePlansRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	ids := make([]int64, 0, len(req.Materials))
	for _, ref := range req.Materials {
		ids = append(ids, ref.ID)
	}
	lines, appErr := service.MovePlansToRecord(h.App.DB, ids, nil, "", "", "", "", "", "已申购", "", nil, nil, nil)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.PurchaseRecordRead, 0, len(lines))
	for i := range lines {
		reads = append(reads, *recordRead(h.App.DB, &lines[i]))
	}
	respond.JSON(c, http.StatusOK, reads)
}

// BatchUpdate PATCH /purchase-materials/batch
func (h *PurchaseMaterialsHandler) BatchUpdate(c *gin.Context) {
	var req dto.BatchUpdatePurchasePlansRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	ids := make([]int64, 0, len(req.Materials))
	versions := make([]int, 0, len(req.Materials))
	for _, ref := range req.Materials {
		ids = append(ids, ref.ID)
		versions = append(versions, ref.Version)
	}
	var planDate *time.Time
	if req.PlanDate != nil {
		if t, err := time.Parse("2006-01-02", *req.PlanDate); err == nil {
			planDate = &t
		}
	}
	items, appErr := service.BatchUpdatePurchaseMaterials(h.App.DB, ids, versions, planDate,
		req.Category, req.Urgency, req.DemandDepartment, req.ActualDemandPerson,
		req.PurchaseResponsible, req.SubitemNo, req.Usage, req.Status)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	movedMap, _ := service.PurchaseMaterialIDsMovedToRecord(h.App.DB, ids)
	reads := make([]dto.PurchaseMaterialRead, 0, len(items))
	for i := range items {
		reads = append(reads, *purchaseRead(h.App.DB, &items[i], movedMap))
	}
	respond.JSON(c, http.StatusOK, reads)
}

// RegisterPurchaseMaterials 注册 /purchase-materials 路由。
func RegisterPurchaseMaterials(r *gin.RouterGroup, app *App) {
	h := NewPurchaseMaterialsHandler(app)
	group := r.Group("/purchase-materials", auth.AuthManagement(app.Cfg, app.DB))
	group.GET("", h.List)
	group.GET("/filter-options", h.FilterOptions)
	group.GET("/:material_id", h.Detail)
	write := group.Group("", auth.PurchaseWriter())
	write.POST("", h.Create)
	write.PATCH("/:material_id", h.Update)
	write.DELETE("/:material_id", h.Delete)
	write.POST("/batch", h.BatchUpdate)
	write.POST("/batch-move-to-record", h.BatchMoveToRecord)
	write.POST("/:material_id/move-to-record", h.MoveToRecord)
	linkWriter := auth.RequireRoles("SUPER_ADMIN", "WAREHOUSE_ADMIN", "PURCHASE_ADMIN")
	write.POST("/:material_id/link-stock-material", linkWriter, h.LinkStockMaterial)
}
