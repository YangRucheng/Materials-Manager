// Package errors 定义统一业务错误类型与状态码映射，等价于
// 与原 Python 实现 _DEFAULT_STATUS_BY_CODE 与 AppError 语义一致。
package errors

import (
	"fmt"
	"net/http"
)

// 默认状态码映射（未显式传 status 时按 code 推断）。
var defaultStatusByCode = map[string]int{
	"NOT_FOUND":                  http.StatusBadRequest, // 400，约定禁用 404
	"VERSION_CONFLICT":           http.StatusConflict,   // 409
	"INVALID_STATUS_TRANSITION":  http.StatusConflict,   // 409
	"DATA_CONFLICT":              http.StatusConflict,   // 409
	"INVALID_TOKEN":              http.StatusUnauthorized,
	"UNAUTHORIZED":               http.StatusUnauthorized,
	"USER_DISABLED":              http.StatusUnauthorized,
	"ACCOUNT_DISABLED":           http.StatusForbidden,
	"FORBIDDEN":                  http.StatusForbidden,
	"VALIDATION_ERROR":           http.StatusUnprocessableEntity, // 422
	"IMPORT_IN_PROGRESS":         http.StatusConflict,
	"AI_RATE_LIMITED":            http.StatusTooManyRequests, // 429
	"AI_UPSTREAM_FAILED":         http.StatusBadGateway,      // 502
	"AI_ENDPOINT_NOT_FOUND":      http.StatusBadRequest,
	"DATABASE_UNAVAILABLE":       http.StatusServiceUnavailable,
	"AI_NOT_CONFIGURED":          http.StatusServiceUnavailable,
	"WECHAT_CONFIGURATION_INVAL": http.StatusServiceUnavailable,
	"WECHAT_NOT_CONFIGURED":      http.StatusServiceUnavailable,
}

// AppError 是统一业务错误。Details 用于携带结构化详情（如版本号、校验错误）。
type AppError struct {
	Code       string
	Message    string
	StatusCode int
	Details    map[string]any
}

func (e *AppError) Error() string {
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

// New 构造 AppError，status 传 0 时按 code 推断默认状态码。
func New(code, message string, status int, details map[string]any) *AppError {
	if status == 0 {
		status = defaultStatusByCode[code]
		if status == 0 {
			status = http.StatusBadRequest
		}
	}
	if details == nil {
		details = map[string]any{}
	}
	return &AppError{Code: code, Message: message, StatusCode: status, Details: details}
}

// NotFound 生成资源不存在错误（HTTP 400 + code=NOT_FOUND）。
func NotFound(resource string) *AppError {
	if resource == "" {
		resource = "资源"
	}
	return New("NOT_FOUND", resource+"不存在", 0, nil)
}

// Validation 生成 422 校验错误。
func Validation(message string, details map[string]any) *AppError {
	return New("VALIDATION_ERROR", message, http.StatusUnprocessableEntity, details)
}

// VersionConflict 生成 409 版本冲突。
func VersionConflict(expected, actual int) *AppError {
	return New("VERSION_CONFLICT", "数据已被其他用户修改，请刷新后重试",
		http.StatusConflict, map[string]any{"expected": expected, "actual": actual})
}

// InvalidTransition 生成 409 非法状态流转。
func InvalidTransition(current, action string) *AppError {
	return New("INVALID_STATUS_TRANSITION", "当前状态不允许执行此操作",
		http.StatusConflict, map[string]any{"current_status": current, "action": action})
}

// AppErrorFrom 把任意 error 包装为 AppError（已是指针原样返回）。
func AppErrorFrom(err error) *AppError {
	if err == nil {
		return nil
	}
	if appErr, ok := err.(*AppError); ok {
		return appErr
	}
	return New("INTERNAL_SERVER_ERROR", "服务内部异常，请联系管理员",
		http.StatusInternalServerError, nil)
}
