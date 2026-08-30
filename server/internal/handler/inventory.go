package handler

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/shopspring/decimal"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/middleware"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// InventoryHandler 库存。
type InventoryHandler struct {
	App *App
}

func NewInventoryHandler(app *App) *InventoryHandler { return &InventoryHandler{App: app} }

func allDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

// queryTime 解析时间筛选参数（毫秒时间戳或 ISO，转 UTC naive；非法 422）。
func queryTime(value string) (*time.Time, *apperrors.AppError) {
	if value == "" {
		return nil, nil
	}
	if allDigits(value) {
		ms, err := strconv.ParseInt(value, 10, 64)
		if err != nil {
			return nil, apperrors.New("VALIDATION_ERROR", "日期筛选参数无效", 422, nil)
		}
		t := time.UnixMilli(ms).UTC()
		return &t, nil
	}
	parsed, err := serialize.ParseDateTime(value)
	if err != nil {
		return nil, apperrors.New("VALIDATION_ERROR", "日期筛选参数无效", 422, nil)
	}
	t := parsed.UTC()
	return &t, nil
}

func trimmedPtr(p *string) *string {
	if p == nil {
		return nil
	}
	v := strings.TrimSpace(*p)
	if v == "" {
		return nil
	}
	return &v
}

// operationRead 组装 StockOperationRead。
func operationRead(item *models.StockOperation) *dto.StockOperationRead {
	lines := make([]dto.StockOperationLineRead, 0, len(item.Lines))
	for _, line := range item.Lines {
		lines = append(lines, dto.StockOperationLineRead{
			ID:              line.ID,
			StockMaterialID: line.StockMaterialID,
			MaterialName:    line.MaterialNameSnapshot,
			ModelSpec:       line.ModelSpecSnapshot,
			UnitName:        line.UnitNameSnapshot,
			Quantity:        serialize.DecimalToString(line.Quantity.Decimal),
			RemainingQty:    serialize.DecimalToString(line.RemainingQty.Decimal),
			BeforeQty:       serialize.DecimalToString(line.BeforeQty.Decimal),
			AfterQty:        serialize.DecimalToString(line.AfterQty.Decimal),
		})
	}
	return &dto.StockOperationRead{
		ID:                  item.ID,
		OperationNo:         item.OperationNo,
		OperationType:       item.OperationType,
		OccurredAt:          serialize.UTCZTime(item.OccurredAt),
		BusinessReason:      item.BusinessReason,
		ReceiverUnit:        item.ReceiverUnit,
		ReceiverName:        item.ReceiverName,
		SubitemNo:           item.SubitemNo,
		SourceType:          service.EffectiveSourceType(item),
		ReversalOfID:        item.ReversalOfID,
		IsReversed:          item.ReversalOfID != nil,
		ClientRequestID:     item.ClientRequestID,
		MiniProgramUserName: item.MiniProgramUserNameSnapshot,
		Lines:               lines,
		CreatedAt:           serialize.UTCZTime(item.CreatedAt),
		Version:             item.Version,
	}
}

// buildOperationInput 组装服务入参。
func buildOperationInput(occurredAt, sourceType, businessReason string, receiverUnit, receiverName, subitemNo *string, lines []dto.OperationLineWrite) (*service.OperationInput, *apperrors.AppError) {
	at, err := serialize.ParseDateTime(occurredAt)
	if err != nil {
		return nil, apperrors.New("VALIDATION_ERROR", "occurred_at 必须是带时区的 ISO 时间", 422, nil)
	}
	input := &service.OperationInput{
		OccurredAt:     at.UTC(),
		SourceType:     sourceType,
		BusinessReason: strings.TrimSpace(businessReason),
		ReceiverUnit:   trimmedPtr(receiverUnit),
		ReceiverName:   trimmedPtr(receiverName),
		SubitemNo:      trimmedPtr(subitemNo),
		Lines:          make([]service.OperationLineInput, 0, len(lines)),
	}
	for _, line := range lines {
		input.Lines = append(input.Lines, service.OperationLineInput{
			StockMaterialID: line.StockMaterialID,
			Quantity:        line.Quantity.Decimal,
		})
	}
	return input, nil
}

// ReplenishmentDefaults GET /inventory/replenishment-defaults
func (h *InventoryHandler) ReplenishmentDefaults(c *gin.Context) {
	responsible, demandDate, appErr := service.ReplenishmentDefaults(h.App.DB)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.ReplenishmentDefaultsRead{
		PurchaseResponsible: responsible,
		DemandDate:          serialize.Date(demandDate),
	})
}

func (h *InventoryHandler) balancesPage(c *gin.Context, lowStockOnly bool) {
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
	var minQty, maxQty *decimal.Decimal
	if !lowStockOnly {
		minQty, appErr = optionalDecimal(c, "min_qty")
		if appErr != nil {
			respond.Error(c, appErr)
			return
		}
		maxQty, appErr = optionalDecimal(c, "max_qty")
		if appErr != nil {
			respond.Error(c, appErr)
			return
		}
	}
	lowStock := false
	if lowStockOnly {
		lowStock = true
	} else if v := c.Query("low_stock"); v != "" {
		lowStock, _ = strconv.ParseBool(v)
	}
	items, total, appErr := service.InventoryBalances(h.App.DB, c.Query("keyword"), minQty, maxQty, lowStock, page, pageSize, nil)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.InventoryBalanceRead]{
		Items: mapBalances(items), Page: page, PageSize: pageSize, Total: total,
	})
}

// Balances GET /inventory/balances
func (h *InventoryHandler) Balances(c *gin.Context) { h.balancesPage(c, false) }

// LowStock GET /inventory/low-stock
func (h *InventoryHandler) LowStock(c *gin.Context) { h.balancesPage(c, true) }

// BalanceDetail GET /inventory/balances/{material_id}
func (h *InventoryHandler) BalanceDetail(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	items, _, appErr := service.InventoryBalances(h.App.DB, "", nil, nil, false, 1, 1, &materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if len(items) == 0 {
		respond.Error(c, apperrors.NotFound("库存物资"))
		return
	}
	respond.JSON(c, http.StatusOK, mapBalances(items)[0])
}

func mapBalances(items []service.InventoryBalanceItem) []dto.InventoryBalanceRead {
	out := make([]dto.InventoryBalanceRead, 0, len(items))
	for _, item := range items {
		var minQty *string
		if item.MinimumQty != nil {
			s := serialize.DecimalToString(*item.MinimumQty)
			minQty = &s
		}
		out = append(out, dto.InventoryBalanceRead{
			StockMaterialID:      item.StockMaterialID,
			Name:                 item.Name,
			Alias:                item.Alias,
			ModelSpec:            item.ModelSpec,
			UnitName:             item.UnitName,
			CurrentQty:           serialize.DecimalToString(item.CurrentQty),
			MinimumQty:           minQty,
			IsLowStock:           item.IsLowStock,
			SuggestedPurchaseQty: serialize.DecimalToString(item.SuggestedPurchaseQty),
			UpdatedAt:            serialize.UTCZTime(item.UpdatedAt),
		})
	}
	return out
}

func optionalDecimal(c *gin.Context, name string) (*decimal.Decimal, *apperrors.AppError) {
	value := c.Query(name)
	if value == "" {
		return nil, nil
	}
	dec, err := serialize.ParseDecimalString(value)
	if err != nil {
		return nil, apperrors.New("VALIDATION_ERROR", name+" 必须是数字", 422, nil)
	}
	return &dec, nil
}

// CreateInbound POST /inventory/inbounds
func (h *InventoryHandler) CreateInbound(c *gin.Context) { h.createOperation(c, "INBOUND") }

// CreateOutbound POST /inventory/outbounds
func (h *InventoryHandler) CreateOutbound(c *gin.Context) { h.createOperation(c, "OUTBOUND") }

func (h *InventoryHandler) createOperation(c *gin.Context, operationType string) {
	var req dto.OperationCreate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	input, appErr := buildOperationInput(req.OccurredAt, req.SourceType, req.BusinessReason,
		req.ReceiverUnit, req.ReceiverName, req.SubitemNo, req.Lines)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	input.ClientRequestID = req.ClientRequestID
	item, appErr := service.CreateOperation(h.App.DB, input, operationType, nil, nil, nil)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusCreated, operationRead(item))
}

// Operations GET /inventory/operations
func (h *InventoryHandler) Operations(c *gin.Context) {
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
	startAt, appErr := queryTime(c.Query("start_at"))
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	endAt, appErr := queryTime(c.Query("end_at"))
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if startAt != nil && endAt != nil && startAt.After(*endAt) {
		respond.Error(c, apperrors.New("VALIDATION_ERROR", "开始时间不能晚于结束时间", 422, nil))
		return
	}
	items, total, appErr := service.SearchOperations(h.App.DB, c.Query("operation_no"),
		c.Query("operation_type"), c.Query("material_name"), c.Query("source_type"),
		startAt, endAt, page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.StockOperationRead, 0, len(items))
	for i := range items {
		reads = append(reads, *operationRead(&items[i]))
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.StockOperationRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// OperationDetail GET /inventory/operations/{operation_id}
func (h *InventoryHandler) OperationDetail(c *gin.Context) {
	operationID, ok := parseIDParam(c, "operation_id")
	if !ok {
		return
	}
	item, appErr := service.GetOperation(h.App.DB, operationID, false)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, operationRead(item))
}

// EditOperation PATCH /inventory/operations/{operation_id}
func (h *InventoryHandler) EditOperation(c *gin.Context) {
	operationID, ok := parseIDParam(c, "operation_id")
	if !ok {
		return
	}
	var req dto.OperationUpdate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	input, appErr := buildOperationInput(req.OccurredAt, req.SourceType, req.BusinessReason,
		req.ReceiverUnit, req.ReceiverName, req.SubitemNo, req.Lines)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	item, appErr := service.GetOperation(h.App.DB, operationID, true)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	updated, appErr := service.UpdateOperation(h.App.DB, item, input, req.Version, req.OperationType)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, operationRead(updated))
}

// ReverseOperation POST /inventory/operations/{operation_id}/reverse
func (h *InventoryHandler) ReverseOperation(c *gin.Context) {
	operationID, ok := parseIDParam(c, "operation_id")
	if !ok {
		return
	}
	var req dto.ReverseOperationRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	input := &service.OperationInput{
		ClientRequestID: req.ClientRequestID,
		BusinessReason:  strings.TrimSpace(req.Reason),
		Lines:           make([]service.OperationLineInput, 0, len(req.Lines)),
	}
	for _, line := range req.Lines {
		input.Lines = append(input.Lines, service.OperationLineInput{
			StockMaterialID: line.StockMaterialID,
			Quantity:        line.Quantity.Decimal,
		})
	}
	original, appErr := service.GetOperation(h.App.DB, operationID, true)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	item, appErr := service.ReverseOperation(h.App.DB, original, input)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, operationRead(item))
}

// CreateReplenishmentDraft POST /inventory/low-stock/{material_id}/create-replenishment-draft
func (h *InventoryHandler) CreateReplenishmentDraft(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	var req dto.ReplenishmentDraftCreate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	demandDate, err := time.Parse("2006-01-02", req.DemandDate)
	if err != nil {
		respond.Error(c, apperrors.New("VALIDATION_ERROR", "demand_date 必须是 YYYY-MM-DD", 422, nil))
		return
	}
	purchase, appErr := service.CreateReplenishmentDraft(h.App.DB, materialID, demandDate,
		req.ActualDemandPerson, req.PurchaseResponsible, req.PlannedQty.Decimal)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.ReplenishmentDraftRead{
		Next:       "purchase_material",
		ResourceID: purchase.ID,
	})
}

// Summary GET /dashboard/summary
func (h *InventoryHandler) Summary(c *gin.Context) {
	stock, low, uncoded, records := service.DashboardSummary(h.App.DB)
	respond.JSON(c, http.StatusOK, dto.DashboardSummaryRead{
		StockMaterialCount:           stock,
		LowStockCount:                low,
		UncodedPurchaseMaterialCount: uncoded,
		PurchaseRecordCount:          records,
	})
}

// RegisterInventory 注册 /inventory 与 /dashboard 路由。
func RegisterInventory(r *gin.RouterGroup, app *App) {
	h := NewInventoryHandler(app)
	group := r.Group("", auth.AuthManagement(app.Cfg, app.DB))
	group.GET("/inventory/replenishment-defaults", h.ReplenishmentDefaults)
	group.GET("/inventory/balances", h.Balances)
	group.GET("/inventory/low-stock", h.LowStock)
	group.GET("/inventory/balances/:material_id", h.BalanceDetail)
	group.GET("/inventory/operations", h.Operations)
	group.GET("/inventory/operations/:operation_id", h.OperationDetail)
	group.GET("/dashboard/summary", h.Summary)

	write := group.Group("", middleware.RequireFullSecondaryWarehouse(app.DB), auth.WarehouseWriter())
	write.POST("/inventory/inbounds", h.CreateInbound)
	write.POST("/inventory/outbounds", h.CreateOutbound)
	write.PATCH("/inventory/operations/:operation_id", h.EditOperation)
	write.POST("/inventory/operations/:operation_id/reverse", h.ReverseOperation)
	write.POST("/inventory/low-stock/:material_id/create-replenishment-draft", h.CreateReplenishmentDraft)
}
