// Package router 注册中间件与路由。
package router

import (
	"net/http"

	"github.com/gin-gonic/gin"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/handler"
	"github.com/yangrucheng/materials-manager/server/internal/middleware"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
)

// New 构造 Gin engine（不含 API v1 路由，由子系统注册）。
func New(app *handler.App) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Logger(), gin.Recovery()) // 基础兜底，随后被自定义覆盖
	// 自定义中间件链（顺序 = 外层优先，与 Python 一致）
	r.Use(middleware.RealIP())
	r.Use(middleware.RequestContext())
	r.Use(middleware.RefererCORS(middleware.NewCORSConfig(app.Cfg)))
	r.Use(middleware.Recovery())

	// 未匹配路径 -> 400 ROUTE_NOT_FOUND（约定禁用 404）
	r.NoRoute(func(c *gin.Context) {
		respond.Error(c, apperrors.New("ROUTE_NOT_FOUND", "接口路径不存在",
			http.StatusBadRequest, nil))
	})
	r.NoMethod(func(c *gin.Context) {
		respond.Error(c, apperrors.New("HTTP_ERROR", "请求方法不允许",
			http.StatusMethodNotAllowed, nil))
	})

	r.GET("/health", app.Health)
	return r
}

// RegisterAPI 注册 /api/v1 下的路由（子系统逐步挂载）。
func RegisterAPI(r *gin.Engine, app *handler.App) {
	v1 := r.Group("/api/v1")
	v1.GET("/openapi.json", app.OpenAPIJSON)
	v1.GET("/version", app.Version)

	handler.RegisterAuth(v1, app)
	handler.RegisterUsers(v1, app)
}
