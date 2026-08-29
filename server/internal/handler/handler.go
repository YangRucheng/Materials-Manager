// Package handler 实现 Gin HTTP 处理器。
package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/openapi"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
)

// App 承载处理器共享依赖（配置 + 数据库）。后续子系统在此挂载 service/repository。
type App struct {
	Cfg *config.Config
	DB  *gorm.DB
}

func NewApp(cfg *config.Config, db *gorm.DB) *App {
	return &App{Cfg: cfg, DB: db}
}

// Health 健康检查：DB SELECT 1 失败返回 503。
func (a *App) Health(c *gin.Context) {
	var result int
	if err := a.DB.Raw("SELECT 1").Scan(&result).Error; err != nil {
		respond.Error(c, apperrors.New("DATABASE_UNAVAILABLE", "数据库连接不可用",
			http.StatusServiceUnavailable, nil))
		return
	}
	respond.JSON(c, http.StatusOK, gin.H{"status": "ok", "database": "ok"})
}

// Version 返回应用版本与构建信息。
func (a *App) Version(c *gin.Context) {
	respond.JSON(c, http.StatusOK, gin.H{
		"app_name":   a.Cfg.AppName,
		"version":    "1.0.0",
		"commit":     nullIfEmpty(a.Cfg.GitSHA),
		"build_time": nullIfEmpty(a.Cfg.BuildTime),
	})
}

func nullIfEmpty(v string) any {
	if v == "" {
		return nil
	}
	return v
}

// OpenAPIJSON 提供 /api/v1/openapi.json。
func (a *App) OpenAPIJSON(c *gin.Context) {
	data, err := openapi.JSON()
	if err != nil {
		respond.Error(c, apperrors.New("INTERNAL_SERVER_ERROR", "OpenAPI 契约解析失败",
			http.StatusInternalServerError, nil))
		return
	}
	c.Data(http.StatusOK, "application/json", data)
}
