package middleware

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// RequireFullSecondaryWarehouse 二级库精简模式下拦截完整模式写接口（防绕过）。
func RequireFullSecondaryWarehouse(db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		if service.IsLiteSecondaryWarehouse(db) {
			respond.Error(c, apperrors.New("SECONDARY_WAREHOUSE_LITE_MODE",
				"精简模式下二级库仅支持导入与查询", http.StatusForbidden, nil))
			c.Abort()
			return
		}
		c.Next()
	}
}
