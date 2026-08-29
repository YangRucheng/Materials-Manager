// Package middleware 提供与 Python 后端一致的 HTTP 中间件链。
// 注册顺序（engine.Use 顺序即外层优先）：
//
//	RealIP -> RequestContext(日志/请求头) -> RefererCORS -> Recovery -> 路由
package middleware

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"log/slog"
	"net"
	"strings"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/config"
)

// RealIP 从受信代理头解析真实客户端 IP（EO-Connecting-IP > X-Real-IP > X-Forwarded-For 首段）。
func RealIP() gin.HandlerFunc {
	return func(c *gin.Context) {
		ip := realIPFromHeaders(c)
		if ip != "" {
			c.Set("client_ip", ip)
		} else if c.ClientIP() != "" {
			c.Set("client_ip", c.ClientIP())
		} else {
			c.Set("client_ip", "unknown")
		}
		c.Next()
	}
}

func realIPFromHeaders(c *gin.Context) string {
	candidates := []string{
		c.GetHeader("EO-Connecting-IP"),
		c.GetHeader("X-Real-IP"),
	}
	if xff := c.GetHeader("X-Forwarded-For"); xff != "" {
		candidates = append(candidates, strings.Split(xff, ",")[0])
	}
	for _, value := range candidates {
		trimmed := strings.TrimSpace(value)
		if trimmed == "" {
			continue
		}
		if ip := net.ParseIP(trimmed); ip != nil {
			return trimmed
		}
	}
	return ""
}

// RequestContext 注入 request_id、计时、写访问日志并回写 X-Request-ID / X-Response-Time。
func RequestContext() gin.HandlerFunc {
	return func(c *gin.Context) {
		requestID := c.GetHeader("X-Request-ID")
		if requestID == "" {
			requestID = newRequestID()
		}
		if len(requestID) > 128 {
			requestID = requestID[:128]
		}
		c.Set("request_id", requestID)
		started := time.Now()
		c.Next()
		elapsedMs := float64(time.Since(started).Nanoseconds()) / 1e6
		c.Header("X-Request-ID", requestID)
		c.Header("X-Response-Time", formatElapsed(elapsedMs))
		clientIP, _ := c.Get("client_ip")
		if clientIP == nil {
			clientIP = "unknown"
		}
		username, _ := c.Get("username")
		if username == nil {
			username = "anonymous"
		}
		slog.Info("HTTP",
			"method", c.Request.Method,
			"path", c.Request.URL.Path,
			"status", c.Writer.Status(),
			"elapsed_ms", elapsedMs,
			"client_ip", clientIP,
			"user", username,
			"request_id", requestID,
		)
	}
}

func newRequestID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "fallback-" + time.Now().UTC().Format("20060102150405.000000000")
	}
	b[6] = (b[6] & 0x0f) | 0x40 // version 4
	b[8] = (b[8] & 0x3f) | 0x80 // variant
	return strings.ToLower(hex.EncodeToString(b[:4]) + "-" + hex.EncodeToString(b[4:6]) +
		"-" + hex.EncodeToString(b[6:8]) + "-" + hex.EncodeToString(b[8:10]) + "-" + hex.EncodeToString(b[10:]))
}

func formatElapsed(ms float64) string {
	return fmt.Sprintf("%.2f", ms)
}

// SetUsername 供认证中间件写入当前用户名（用于访问日志）。
func SetUsername(c *gin.Context, username string) { c.Set("username", username) }

// Username 读取当前用户名。
func Username(c *gin.Context) string {
	if v, ok := c.Get("username"); ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return "anonymous"
}

// Config 供 CORS 中间件使用。
type Config struct {
	CORSOrigins          []string
	CORSAllowCredentials bool
	CORSMaxAge           int
}

// NewCORSConfig 从全局配置构造。
func NewCORSConfig(cfg *config.Config) *Config {
	return &Config{
		CORSOrigins:          cfg.CORSOrigins,
		CORSAllowCredentials: cfg.CORSAllowCredentials,
		CORSMaxAge:           cfg.CORSMaxAge,
	}
}
