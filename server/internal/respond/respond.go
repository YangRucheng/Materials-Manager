// Package respond 提供统一 JSON 响应与错误响应构造（等价 FastAPI error_response）。
package respond

import (
	"net/http"

	"github.com/gin-gonic/gin"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
)

// ErrorBody 结构化业务错误体。
type ErrorBody struct {
	Code      string `json:"code"`
	Message   string `json:"message"`
	Details   any    `json:"details"`
	RequestID string `json:"request_id"`
}

// RequestID 读取请求上下文中的 request_id。
func RequestID(c *gin.Context) string {
	if v, ok := c.Get("request_id"); ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return "unknown"
}

// Error 输出统一错误响应。
func Error(c *gin.Context, appErr *apperrors.AppError) {
	if appErr == nil {
		appErr = apperrors.New("INTERNAL_SERVER_ERROR", "服务内部异常，请联系管理员",
			http.StatusInternalServerError, nil)
	}
	details := appErr.Details
	if details == nil {
		details = map[string]any{}
	}
	c.JSON(appErr.StatusCode, ErrorBody{
		Code:      appErr.Code,
		Message:   appErr.Message,
		Details:   details,
		RequestID: RequestID(c),
	})
}

// Errorf 用 code/message 构造并输出错误。
func Errorf(c *gin.Context, status int, code, message string) {
	Error(c, apperrors.New(code, message, status, nil))
}

// JSON 输出任意 JSON（保持 c.JSON 语义）。
func JSON(c *gin.Context, status int, data any) {
	c.JSON(status, data)
}
