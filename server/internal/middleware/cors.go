package middleware

import (
	"net/url"
	"strings"

	"github.com/gin-gonic/gin"
)

// 与原 Python 实现的 RefererCORSMiddleware 语义一致：
// Referer 优先，Origin 回退；仅回显白名单内的来源；OPTIONS 预检直接返回。
var allowMethods = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
var exposeHeaders = "Content-Disposition, X-Request-ID, X-Response-Time"

// RefererCORS 处理跨域。
func RefererCORS(cfg *Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := corsOrigin(c, cfg.CORSOrigins)
		if origin == "" {
			c.Next()
			return
		}
		// 预检
		if c.Request.Method == "OPTIONS" && c.GetHeader("Access-Control-Request-Method") != "" {
			c.Header("Access-Control-Allow-Origin", origin)
			c.Header("Access-Control-Allow-Methods", allowMethods)
			c.Header("Access-Control-Max-Age", itoa(cfg.CORSMaxAge))
			c.Header("Access-Control-Expose-Headers", exposeHeaders)
			c.Header("Vary", "Origin, Referer")
			if cfg.CORSAllowCredentials {
				c.Header("Access-Control-Allow-Credentials", "true")
			}
			if requested := c.GetHeader("Access-Control-Request-Headers"); requested != "" {
				c.Header("Access-Control-Allow-Headers", requested)
			}
			if c.GetHeader("Access-Control-Request-Private-Network") == "true" {
				c.Header("Access-Control-Allow-Private-Network", "true")
			}
			c.AbortWithStatus(200)
			return
		}
		// 普通请求：回写头，继续
		c.Header("Access-Control-Allow-Origin", origin)
		if cfg.CORSAllowCredentials {
			c.Header("Access-Control-Allow-Credentials", "true")
		}
		c.Header("Access-Control-Expose-Headers", exposeHeaders)
		c.Header("Vary", "Origin, Referer")
		c.Next()
	}
}

func itoa(v int) string {
	if v == 0 {
		return "0"
	}
	neg := v < 0
	u := uint64(v)
	if neg {
		u = uint64(-v)
	}
	var buf [20]byte
	i := len(buf)
	for u > 0 {
		i--
		buf[i] = byte('0' + u%10)
		u /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}

func corsOrigin(c *gin.Context, allowedOrigins []string) string {
	origin := originFromURL(c.GetHeader("Referer"))
	if origin == "" {
		origin = originFromURL(c.GetHeader("Origin"))
	}
	if origin == "" {
		return ""
	}
	if len(allowedOrigins) == 0 || isAllowedOrigin(origin, allowedOrigins) {
		return origin
	}
	return ""
}

func originFromURL(value string) string {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return ""
	}
	if trimmed == "null" {
		return "null"
	}
	parsed, err := url.Parse(trimmed)
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		return ""
	}
	return strings.ToLower(parsed.Scheme) + "://" + strings.ToLower(parsed.Host)
}

func isAllowedOrigin(origin string, allowedOrigins []string) bool {
	for _, allowed := range allowedOrigins {
		low := strings.ToLower(allowed)
		if low == "*" || low == origin {
			return true
		}
		if strings.HasPrefix(low, ".") && strings.HasSuffix(origin, low) {
			return true
		}
	}
	return false
}
