// Package config 加载后端运行配置。环境变量前缀 APP_，变量名与 Python 后端
// （backend/app/core/config.py）完全一致，保证 docker-compose 环境变量零改动。
package config

import (
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// 默认常量（与 Python Settings 默认值一致）。
const (
	DefaultAppName             = "电气车间备件管理系统"
	DefaultEnvironment         = "development"
	DefaultDatabaseURL         = "mysql+asyncmy://spare:spare@mysql:3306/spare_parts?charset=utf8mb4"
	DefaultJWTSecret           = "change-me-in-production"
	DefaultJWTAlgorithm        = "HS256"
	DefaultAccessTokenMinutes  = 30
	DefaultRefreshTokenDays    = 7
	DefaultUploadDir           = "data/uploads"
	DefaultTemplateDir         = "templates"
	DefaultLogDir              = "data/logs"
	DefaultLogBackupCount      = 90
	DefaultMaxImageBytes       = 10 * 1024 * 1024
	DefaultCORSAllowCredential = true
	DefaultCORSMaxAge          = 86400
)

// Config 是进程级全局配置单例（等价于 Python 的 get_settings()）。
type Config struct {
	AppName                    string
	Environment                string
	DatabaseURL                string
	JWTSecret                  string
	JWTAlgorithm               string
	AccessTokenMinutes         int
	RefreshTokenDays           int
	FernetKey                  string
	WechatMiniProgramAppID     string
	WechatMiniProgramAppSecret string
	UploadDir                  string
	TemplateDir                string
	LogDir                     string
	LogBackupCount             int
	MaxImageBytes              int64
	CORSOrigins                []string
	CORSAllowCredentials       bool
	CORSMaxAge                 int
	PurchasePlanCleanupEnabled bool
	BuildTime                  string
	GitSHA                     string

	// 派生的可写目录（启动时 mkdir）。
	UploadDirPath string
	LogDirPath    string
}

func env(key, def string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return def
}

func envInt(key string, def int) int {
	if v, ok := os.LookupEnv(key); ok {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func envBool(key string, def bool) bool {
	if v, ok := os.LookupEnv(key); ok {
		if b, err := strconv.ParseBool(v); err == nil {
			return b
		}
	}
	return def
}

// Load 从环境变量加载配置。rootDir 为仓库/容器内的工作目录，
// 用于解析相对 upload/log/template 目录（与 Python BACKEND_DIR 语义对齐）。
func Load(rootDir string) *Config {
	cfg := &Config{
		AppName:                    env("APP_NAME", DefaultAppName),
		Environment:                env("APP_ENVIRONMENT", DefaultEnvironment),
		DatabaseURL:                env("APP_DATABASE_URL", DefaultDatabaseURL),
		JWTSecret:                  env("APP_JWT_SECRET", DefaultJWTSecret),
		JWTAlgorithm:               env("APP_JWT_ALGORITHM", DefaultJWTAlgorithm),
		AccessTokenMinutes:         envInt("APP_ACCESS_TOKEN_MINUTES", DefaultAccessTokenMinutes),
		RefreshTokenDays:           envInt("APP_REFRESH_TOKEN_DAYS", DefaultRefreshTokenDays),
		FernetKey:                  env("APP_FERNET_KEY", ""),
		WechatMiniProgramAppID:     env("APP_WECHAT_MINI_PROGRAM_APP_ID", ""),
		WechatMiniProgramAppSecret: env("APP_WECHAT_MINI_PROGRAM_APP_SECRET", ""),
		LogBackupCount:             envInt("APP_LOG_BACKUP_COUNT", DefaultLogBackupCount),
		MaxImageBytes:              int64(envInt("APP_MAX_IMAGE_BYTES", DefaultMaxImageBytes)),
		CORSAllowCredentials:       envBool("APP_CORS_ALLOW_CREDENTIALS", DefaultCORSAllowCredential),
		CORSMaxAge:                 envInt("APP_CORS_MAX_AGE", DefaultCORSMaxAge),
		PurchasePlanCleanupEnabled: envBool("APP_PURCHASE_PLAN_CLEANUP_ENABLED", true),
		BuildTime:                  env("APP_BUILD_TIME", ""),
		GitSHA:                     env("APP_GIT_SHA", ""),
	}
	cfg.UploadDir = env("APP_UPLOAD_DIR", filepath.Join(rootDir, DefaultUploadDir))
	cfg.TemplateDir = env("APP_TEMPLATE_DIR", filepath.Join(rootDir, DefaultTemplateDir))
	cfg.LogDir = env("APP_LOG_DIR", filepath.Join(rootDir, DefaultLogDir))
	cfg.CORSOrigins = parseCORSOrigins(env("APP_CORS_ORIGINS", ""))
	cfg.UploadDirPath = cfg.UploadDir
	cfg.LogDirPath = cfg.LogDir
	return cfg
}

func parseCORSOrigins(value string) []string {
	var out []string
	for _, item := range strings.Split(value, ",") {
		if trimmed := strings.TrimSpace(item); trimmed != "" {
			out = append(out, trimmed)
		}
	}
	return out
}

// MySQLDSN 把 Python 风格的 database_url 转换为 Go MySQL DSN。
// 例：mysql+asyncmy://user:pass@host:3306/db?charset=utf8mb4
//
//	-> user:pass@tcp(host:3306)/db?charset=utf8mb4&parseTime=true&loc=UTC
func MySQLDSN(databaseURL string) (string, bool) {
	rest := strings.TrimPrefix(databaseURL, "mysql+asyncmy://")
	if rest == databaseURL {
		rest = strings.TrimPrefix(databaseURL, "mysql://")
		if rest == databaseURL {
			return "", false
		}
	}
	// 拆 query
	base, queryPart, hasQuery := strings.Cut(rest, "?")
	// 拆 user:pass@host:port/db
	at := strings.LastIndex(base, "@")
	var creds, hostDB string
	if at >= 0 {
		creds = base[:at]
		hostDB = base[at+1:]
	} else {
		creds = ""
		hostDB = base
	}
	host, dbName, _ := strings.Cut(hostDB, "/")
	q := url.Values{}
	if hasQuery {
		for _, pair := range strings.Split(queryPart, "&") {
			k, v, _ := strings.Cut(pair, "=")
			if k != "" {
				q.Add(k, v)
			}
		}
	}
	q.Set("parseTime", "true")
	q.Set("loc", "UTC")
	return creds + "@tcp(" + host + ")/" + dbName + "?" + q.Encode(), true
}

// SQLitePath 判断是否为 SQLite（内存或文件），返回 GORM SQLite DSN。
func SQLitePath(databaseURL string) (string, bool) {
	rest := strings.TrimPrefix(databaseURL, "sqlite+aiosqlite:///")
	if rest == databaseURL {
		return "", false
	}
	if rest == ":memory:" {
		return "file::memory:?cache=shared", true
	}
	return rest, true
}

// TokenExpireAccess / TokenExpireRefresh 返回令牌有效期。
func (c *Config) TokenExpireAccess() time.Duration {
	return time.Duration(c.AccessTokenMinutes) * time.Minute
}

func (c *Config) TokenExpireRefresh() time.Duration {
	return time.Duration(c.RefreshTokenDays) * 24 * time.Hour
}
