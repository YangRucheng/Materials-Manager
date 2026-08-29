package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// AuthHandler 认证相关端点。
type AuthHandler struct {
	App *App
}

func NewAuthHandler(app *App) *AuthHandler { return &AuthHandler{App: app} }

// Login POST /auth/login
func (h *AuthHandler) Login(c *gin.Context) {
	var req dto.LoginRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	user, access, refresh, appErr := service.Login(h.App.Cfg, h.App.DB, req.Username, req.Password)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.LoginResponse{
		AccessToken:  access,
		RefreshToken: refresh,
		TokenType:    "bearer",
		User:         dto.NewUserRead(user),
	})
}

// Refresh POST /auth/refresh
func (h *AuthHandler) Refresh(c *gin.Context) {
	var req dto.RefreshTokenRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	access, refresh, appErr := service.Refresh(h.App.Cfg, h.App.DB, req.RefreshToken)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.TokenPairResponse{
		AccessToken:  access,
		RefreshToken: refresh,
		TokenType:    "bearer",
	})
}

// Me GET /auth/me
func (h *AuthHandler) Me(c *gin.Context) {
	user := auth.CurrentUser(c)
	respond.JSON(c, http.StatusOK, dto.NewUserRead(user))
}

// RegisterAuth 注册 /auth 路由。
func RegisterAuth(r *gin.RouterGroup, app *App) {
	h := NewAuthHandler(app)
	group := r.Group("/auth")
	group.POST("/login", h.Login)
	group.POST("/refresh", h.Refresh)
	group.GET("/me", auth.AuthManagement(app.Cfg, app.DB), h.Me)
}
