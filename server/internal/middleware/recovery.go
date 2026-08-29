package middleware

import (
	"log/slog"
	"net/http"

	"github.com/gin-gonic/gin"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
)

// Recovery 捕获 panic，输出 500 INTERNAL_SERVER_ERROR（等价 handle_unexpected_error）。
func Recovery() gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if r := recover(); r != nil {
				slog.Error("panic recovered",
					"panic", r,
					"path", c.Request.URL.Path,
					"request_id", respond.RequestID(c))
				respond.Error(c, apperrors.New("INTERNAL_SERVER_ERROR",
					"服务内部异常，请联系管理员", http.StatusInternalServerError, nil))
				c.Abort()
			}
		}()
		c.Next()
	}
}
