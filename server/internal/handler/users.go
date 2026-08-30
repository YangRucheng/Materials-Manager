package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// UsersHandler 基础数据（用户管理）。
type UsersHandler struct {
	App *App
}

func NewUsersHandler(app *App) *UsersHandler { return &UsersHandler{App: app} }

// List GET /users（SuperAdmin）
func (h *UsersHandler) List(c *gin.Context) {
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
	items, total, appErr := service.ListUsers(h.App.DB, c.Query("keyword"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	readItems := make([]dto.UserApiTokenRead, 0, len(items))
	for i := range items {
		readItems = append(readItems, dto.NewUserApiTokenRead(&items[i]))
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.UserApiTokenRead]{
		Items: readItems, Page: page, PageSize: pageSize, Total: total,
	})
}

// Create POST /users（SuperAdmin）
func (h *UsersHandler) Create(c *gin.Context) {
	var req dto.UserCreate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	enabled := true
	if req.Enabled != nil {
		enabled = *req.Enabled
	}
	user, appErr := service.CreateUser(h.App.DB, req.Username, req.Password, req.DisplayName, req.Role, enabled)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusCreated, dto.NewUserApiTokenRead(user))
}

// Update PATCH /users/{item_id}（SuperAdmin）
func (h *UsersHandler) Update(c *gin.Context) {
	itemID, ok := parseID(c)
	if !ok {
		return
	}
	var req dto.UserUpdate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	user, appErr := service.UpdateUser(h.App.DB, itemID, req.Username, req.DisplayName, req.Password, req.Role, req.Enabled, req.Version)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.NewUserApiTokenRead(user))
}

// RegenerateToken POST /users/{item_id}/api-token/regenerate（SuperAdmin）
func (h *UsersHandler) RegenerateToken(c *gin.Context) {
	itemID, ok := parseID(c)
	if !ok {
		return
	}
	var req dto.UserApiTokenRegenerate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	user, appErr := service.RegenerateAPIToken(h.App.DB, itemID, req.Version)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.NewUserApiTokenRead(user))
}

// Delete DELETE /users/{item_id}（SuperAdmin）
func (h *UsersHandler) Delete(c *gin.Context) {
	itemID, ok := parseID(c)
	if !ok {
		return
	}
	currentUser := auth.CurrentUser(c)
	var currentUserID int64
	if currentUser != nil {
		currentUserID = currentUser.ID
	}
	if appErr := service.DeleteUser(h.App.DB, itemID, currentUserID); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	c.Status(http.StatusNoContent)
}

// parseID 解析路径参数 :item_id。
func parseID(c *gin.Context) (int64, bool) {
	raw := c.Param("item_id")
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		respond.Error(c, apperrors.New("VALIDATION_ERROR", "无效的 ID 参数", 422, nil))
		return 0, false
	}
	return id, true
}

// RegisterUsers 注册 /users 路由（SuperAdmin）。
func RegisterUsers(r *gin.RouterGroup, app *App) {
	h := NewUsersHandler(app)
	group := r.Group("/users", auth.AuthManagement(app.Cfg, app.DB), auth.SuperAdmin())
	group.GET("", h.List)
	group.POST("", h.Create)
	group.PATCH("/:item_id", h.Update)
	group.POST("/:item_id/api-token/regenerate", h.RegenerateToken)
	group.DELETE("/:item_id", h.Delete)
}
