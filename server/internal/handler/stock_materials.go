package handler

import (
	"net/http"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/middleware"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// StockMaterialsHandler 二级库物资。
type StockMaterialsHandler struct {
	App *App
}

func NewStockMaterialsHandler(app *App) *StockMaterialsHandler {
	return &StockMaterialsHandler{App: app}
}

// stockRead 组装 StockMaterialRead。
func (h *StockMaterialsHandler) stockRead(item *service.StockMaterialWithBalance) *dto.StockMaterialRead {
	images := make([]dto.FileObjectRead, 0, len(item.Images))
	for i := range item.Images {
		images = append(images, dto.NewFileObjectRead(&item.Images[i]))
	}
	read := &dto.StockMaterialRead{
		ID:                  item.Material.ID,
		UUID:                item.Material.UUID,
		Name:                item.Material.Name,
		NameID:              item.Material.NameID,
		Alias:               item.Material.Alias,
		ModelSpec:           item.Material.ModelSpec,
		UnitName:            item.Material.UnitName,
		Remark:              item.Material.Remark,
		CurrentQty:          serialize.DecimalToString(item.BalanceQty),
		Images:              images,
		HasOperationRecords: item.HasOperations,
		CreatedAt:           serialize.UTCZTime(item.Material.CreatedAt),
		UpdatedAt:           serialize.UTCZTime(item.Material.UpdatedAt),
		Version:             item.Material.Version,
	}
	if item.Policy != nil {
		read.ReplenishmentPolicy = &dto.ReplenishmentPolicyRead{
			MinimumQty: serialize.DecimalToString(item.Policy.MinimumQty.Decimal),
			Enabled:    item.Policy.Enabled,
			Version:    item.Policy.Version,
		}
	}
	return read
}

// List GET /stock-materials
func (h *StockMaterialsHandler) List(c *gin.Context) {
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
	items, total, appErr := service.SearchStockMaterials(h.App.DB, c.Query("keyword"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.StockMaterialRead, 0, len(items))
	for i := range items {
		full, appErr := service.LoadStockMaterialDetail(h.App.DB, items[i].ID)
		if appErr != nil {
			respond.Error(c, appErr)
			return
		}
		reads = append(reads, *h.stockRead(full))
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.StockMaterialRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// Create POST /stock-materials
func (h *StockMaterialsHandler) Create(c *gin.Context) {
	var req dto.StockMaterialCreate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	item, appErr := service.CreateStockMaterial(h.App.DB, req.Name, ptrValue(req.NameID), ptrValue(req.Alias),
		req.ModelSpec, req.UnitName, ptrValue(req.Remark), req.ImageIDs)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	full, appErr := service.LoadStockMaterialDetail(h.App.DB, item.ID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusCreated, h.stockRead(full))
}

// Detail GET /stock-materials/{material_id}
func (h *StockMaterialsHandler) Detail(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	full, appErr := service.LoadStockMaterialDetail(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, h.stockRead(full))
}

// Update PATCH /stock-materials/{material_id}
func (h *StockMaterialsHandler) Update(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	var req dto.StockMaterialUpdate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	item, appErr := service.GetStockMaterial(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	_, appErr = service.UpdateStockMaterial(h.App.DB, item, req.Name, ptrValue(req.NameID), ptrValue(req.Alias),
		req.ModelSpec, req.UnitName, ptrValue(req.Remark), req.ImageIDs, req.Version)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	full, appErr := service.LoadStockMaterialDetail(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, h.stockRead(full))
}

// Delete DELETE /stock-materials/{material_id}
func (h *StockMaterialsHandler) Delete(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	version := parseIfMatch(c)
	item, appErr := service.GetStockMaterial(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if appErr := service.DeleteStockMaterial(h.App.DB, item, version); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	c.Status(http.StatusNoContent)
}

// SavePolicy PUT /stock-materials/{material_id}/replenishment-policy
func (h *StockMaterialsHandler) SavePolicy(c *gin.Context) {
	materialID, ok := parseIDParam(c, "material_id")
	if !ok {
		return
	}
	var req dto.ReplenishmentPolicyWrite
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	minQty, err := serialize.ParseDecimalString(req.MinimumQty)
	if err != nil {
		respond.Error(c, apperrors.New("VALIDATION_ERROR", "无效的安全库存数量", 422, nil))
		return
	}
	item, appErr := service.GetStockMaterial(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if appErr := service.SetReplenishmentPolicy(h.App.DB, item, minQty, req.Enabled, req.Version); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	full, appErr := service.LoadStockMaterialDetail(h.App.DB, materialID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, h.stockRead(full))
}

// RegisterStockMaterials 注册 /stock-materials 路由。
func RegisterStockMaterials(r *gin.RouterGroup, app *App) {
	h := NewStockMaterialsHandler(app)
	group := r.Group("/stock-materials", auth.AuthManagement(app.Cfg, app.DB))
	group.GET("", h.List)
	group.GET("/:material_id", h.Detail)
	write := group.Group("", middleware.RequireFullSecondaryWarehouse(app.DB))
	write.POST("", auth.WarehouseWriter(), h.Create)
	write.PATCH("/:material_id", auth.WarehouseWriter(), h.Update)
	write.DELETE("/:material_id", auth.WarehouseWriter(), h.Delete)
	write.PUT("/:material_id/replenishment-policy", auth.WarehouseWriter(), h.SavePolicy)
}

// 辅助
func ptrValue(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func parseIDParam(c *gin.Context, name string) (int64, bool) {
	raw := c.Param(name)
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		respond.Error(c, apperrors.New("VALIDATION_ERROR", "无效的 ID 参数", 422, nil))
		return 0, false
	}
	return id, true
}

func parseIfMatch(c *gin.Context) int {
	value := c.GetHeader("If-Match")
	if value == "" {
		return 0
	}
	trimmed := strings.Trim(strings.TrimSpace(value), `"`)
	n, err := strconv.Atoi(trimmed)
	if err != nil {
		return 0
	}
	return n
}
