package handler

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// PurchaseRequestsHandler 申购记录。
type PurchaseRequestsHandler struct {
	App *App
}

func NewPurchaseRequestsHandler(app *App) *PurchaseRequestsHandler {
	return &PurchaseRequestsHandler{App: app}
}

// List GET /purchase-records
func (h *PurchaseRequestsHandler) List(c *gin.Context) {
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
	lines, total, appErr := service.SearchPurchaseRecords(h.App.DB, c.Query("record_status"),
		parseBool(c, "empty_status"), c.Query("keyword"), c.Query("search_field"),
		c.Query("search_value"), c.Query("purchase_order_no"), c.Query("trace_no"),
		c.Query("category"), c.Query("name"), c.Query("model_spec"),
		c.Query("actual_demand_person"), c.Query("purchase_responsible"), c.Query("salesperson"),
		c.Query("subitem_no"), parseBool(c, "empty_subitem_no"), page, pageSize,
		c.Query("sort_by"), c.Query("sort_order"))
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.PurchaseRecordRead, 0, len(lines))
	for i := range lines {
		reads = append(reads, *recordRead(h.App.DB, &lines[i]))
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.PurchaseRecordRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// FilterOptions GET /purchase-records/filter-options
func (h *PurchaseRequestsHandler) FilterOptions(c *gin.Context) {
	persons, responsibles, subitems, categories, _ := service.PurchaseFilterOptions(h.App.DB, nil, nil)
	salespersons, statuses, _ := service.RecordFilterOptions(h.App.DB)
	respond.JSON(c, http.StatusOK, dto.PurchaseRecordFilterOptions{
		ActualDemandPersons: persons, PurchaseResponsibles: responsibles,
		SubitemNos: subitems, Categories: categories, Salespersons: salespersons, Statuses: statuses,
	})
}

// Detail GET /purchase-records/{line_id}
func (h *PurchaseRequestsHandler) Detail(c *gin.Context) {
	lineID, ok := parseIDParam(c, "line_id")
	if !ok {
		return
	}
	line, appErr := service.GetPurchaseRecord(h.App.DB, lineID, false)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, recordRead(h.App.DB, line))
}

// Update PATCH /purchase-records/{line_id}
func (h *PurchaseRequestsHandler) Update(c *gin.Context) {
	lineID, ok := parseIDParam(c, "line_id")
	if !ok {
		return
	}
	var req dto.PurchaseRecordUpdate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	line, appErr := service.GetPurchaseRecord(h.App.DB, lineID, true)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	request := line.Request
	planDate, err := time.Parse("2006-01-02", req.PlanDate)
	if err != nil {
		respond.Error(c, appErrNew("VALIDATION_ERROR", "plan_date 必须是 YYYY-MM-DD", 422, nil))
		return
	}
	updated, appErr := service.UpdatePurchaseRecord(h.App.DB, line, request, planDate,
		derefStr(req.MaterialCode), derefStr(req.Category), req.DemandDepartment, req.MaterialName,
		req.ModelSpec, req.UnitName, req.ActualDemandPerson, req.PurchaseResponsible,
		req.PurchaseQty.Decimal, req.Usage, derefStr(req.SubitemNo), derefStr(req.Salesperson),
		req.Status, req.ImageIDs, req.Version)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, recordRead(h.App.DB, updated))
}

// BatchUpdate PATCH /purchase-records/batch
func (h *PurchaseRequestsHandler) BatchUpdate(c *gin.Context) {
	var req dto.BatchUpdatePurchaseRecordsRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	lineIDs := make([]int64, 0, len(req.Lines))
	versions := make([]int, 0, len(req.Lines))
	for _, ref := range req.Lines {
		lineIDs = append(lineIDs, ref.ID)
		versions = append(versions, ref.Version)
	}
	lines, appErr := service.BatchUpdatePurchaseRecords(h.App.DB, lineIDs, versions,
		req.PurchaseOrderNo, req.ContractNo, req.VesselNo, req.ConsolidationPort, req.Salesperson,
		req.Status, parseOptionalDate(req.ConsolidationDate), parseOptionalDate(req.SailingDate),
		parseOptionalDate(req.PurchaseDate))
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

func parseOptionalDate(s *string) *time.Time {
	if s == nil {
		return nil
	}
	if t, err := time.Parse("2006-01-02", *s); err == nil {
		return &t
	}
	return nil
}

// RestoreToPlan POST /purchase-records/{line_id}/restore-to-plan
func (h *PurchaseRequestsHandler) RestoreToPlan(c *gin.Context) {
	lineID, ok := parseIDParam(c, "line_id")
	if !ok {
		return
	}
	line, appErr := service.GetPurchaseRecord(h.App.DB, lineID, true)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	material, appErr := service.RestorePurchaseRecordToPlan(h.App.DB, line, parseIfMatch(c))
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, purchaseRead(h.App.DB, material, nil))
}

// RegisterPurchaseRequests 注册 /purchase-records 路由。
func RegisterPurchaseRequests(r *gin.RouterGroup, app *App) {
	h := NewPurchaseRequestsHandler(app)
	group := r.Group("/purchase-records", auth.AuthManagement(app.Cfg, app.DB))
	group.GET("", h.List)
	group.GET("/filter-options", h.FilterOptions)
	group.GET("/:line_id", h.Detail)
	write := group.Group("", auth.PurchaseWriter())
	write.PATCH("/:line_id", h.Update)
	write.PATCH("/batch", h.BatchUpdate)
	write.POST("/:line_id/restore-to-plan", h.RestoreToPlan)
}
