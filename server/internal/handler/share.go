package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/domain"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// ShareHandler 链接分享。
type ShareHandler struct {
	App *App
}

func NewShareHandler(app *App) *ShareHandler { return &ShareHandler{App: app} }

func shareRead(share *modelsShareLink) *dto.ShareRead {
	var expires *serialize.UTCZTime
	if share.ExpiresAt != nil {
		t := serialize.UTCZTime(*share.ExpiresAt)
		expires = &t
	}
	var columns []string
	_ = service.DecodeJSON(share.Columns, &columns)
	return &dto.ShareRead{
		Token: share.Token, ShareType: service.ShareTypeValue(share.ShareType),
		ItemCount: shareItemCount(share), ExpiresAt: expires,
		CreatedAt: serialize.UTCZTime(share.CreatedAt), Columns: columns,
	}
}

func shareItemCount(share *modelsShareLink) int {
	var ids []int64
	_ = service.DecodeJSON(share.ItemIDs, &ids)
	return len(ids)
}

// List GET /shares
func (h *ShareHandler) List(c *gin.Context) {
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
	shares, names, total, appErr := service.ListShares(h.App.DB, user.ID, isSuper, page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items := make([]dto.ShareListRead, 0, len(shares))
	for i, share := range shares {
		var expires *serialize.UTCZTime
		if share.ExpiresAt != nil {
			t := serialize.UTCZTime(*share.ExpiresAt)
			expires = &t
		}
		var columns []string
		_ = service.DecodeJSON(share.Columns, &columns)
		var createdBy *int64
		if share.CreatedBy != nil {
			createdBy = share.CreatedBy
		}
		items = append(items, dto.ShareListRead{
			Token: share.Token, ShareType: service.ShareTypeValue(share.ShareType),
			ItemCount: shareItemCount(&share), ExpiresAt: expires,
			CreatedAt: serialize.UTCZTime(share.CreatedAt), CreatedBy: createdBy,
			CreatedByName: names[i], Columns: columns,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.ShareListRead]{
		Items: items, Page: page, PageSize: pageSize, Total: total,
	})
}

// Create POST /shares
func (h *ShareHandler) Create(c *gin.Context) {
	var req dto.ShareCreateRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	user := auth.CurrentUser(c)
	share, appErr := service.CreateShare(h.App.DB, req.ShareType, req.ItemIDs, req.ExpiresIn, user.ID, req.Columns)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusCreated, shareRead(share))
}

// GetPublic GET /shares/{token}（匿名）
func (h *ShareHandler) GetPublic(c *gin.Context) {
	token := c.Param("token")
	share, extra, appErr := service.GetPublicShare(h.App.DB, token)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	columns := resolveShareColumns(share)
	items := extra["items"].([]map[string]any)
	respond.JSON(c, http.StatusOK, dto.SharePublicView{
		ShareType: service.ShareTypeValue(share.ShareType), Columns: columns, Items: toAnySlice(items),
	})
}

func resolveShareColumns(share *modelsShareLink) []string {
	var columns []string
	_ = service.DecodeJSON(share.Columns, &columns)
	if columns != nil {
		return columns
	}
	// 默认集合：全部列去掉「状态」
	allowed := shareAllowedKeys(service.ShareTypeValue(share.ShareType))
	out := make([]string, 0, len(allowed))
	for key := range allowed {
		if key == "status" {
			continue
		}
		out = append(out, key)
	}
	return out
}

func shareAllowedKeys(shareType string) map[string]bool {
	if shareType == domain.SharePurchasePlan {
		return map[string]bool{
			"plan_date": true, "material_code": true, "category": true, "urgency": true,
			"demand_department": true, "name": true, "model_spec": true, "planned_qty": true,
			"actual_demand_person": true, "purchase_responsible": true, "subitem_no": true,
			"usage": true, "status": true, "images": true, "unit_name": true,
		}
	}
	return map[string]bool{
		"plan_date": true, "purchase_order_no": true, "trace_no": true, "category": true,
		"demand_department": true, "material_name": true, "model_spec": true, "purchase_qty": true,
		"actual_demand_person": true, "purchase_responsible": true, "salesperson": true,
		"subitem_no": true, "usage": true, "status": true, "images": true, "unit_name": true,
	}
}

func toAnySlice(items []map[string]any) []any {
	out := make([]any, 0, len(items))
	for _, m := range items {
		out = append(out, m)
	}
	return out
}

// Update PATCH /shares/{token}
func (h *ShareHandler) Update(c *gin.Context) {
	token := c.Param("token")
	var req dto.ShareUpdateRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	user := auth.CurrentUser(c)
	isSuper := user != nil && user.Role == domain.RoleSuperAdmin
	share, appErr := service.UpdateShare(h.App.DB, token, user.ID, isSuper, req.Columns, req.ExpiresIn)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, shareRead(share))
}

// Revoke DELETE /shares/{token}
func (h *ShareHandler) Revoke(c *gin.Context) {
	token := c.Param("token")
	user := auth.CurrentUser(c)
	isSuper := user != nil && user.Role == domain.RoleSuperAdmin
	if appErr := service.RevokeShare(h.App.DB, token, user.ID, isSuper); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	c.Status(http.StatusNoContent)
}

// RegisterShares 注册 /shares 路由。
func RegisterShares(r *gin.RouterGroup, app *App) {
	h := NewShareHandler(app)
	// 匿名读取
	r.GET("/shares/:token", h.GetPublic)
	group := r.Group("/shares", auth.AuthManagement(app.Cfg, app.DB))
	group.GET("", h.List)
	group.POST("", h.Create)
	group.PATCH("/:token", h.Update)
	group.DELETE("/:token", h.Revoke)
}
