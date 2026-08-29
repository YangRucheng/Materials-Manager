// Package testutil 提供 Go 后端集成测试的共享设施：
// 内存 SQLite + 按模型建表 + 种子账号 + httptest 客户端。
package testutil

import (
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/database"
	"github.com/yangrucheng/materials-manager/server/internal/handler"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/router"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

// NewTestConfig 构造测试配置（SQLite 内存 + 固定 JWT 密钥）。
func NewTestConfig(t *testing.T) *config.Config {
	t.Helper()
	cfg := config.Load(".")
	cfg.DatabaseURL = "sqlite+aiosqlite:///:memory:"
	cfg.JWTSecret = "test-secret-that-is-long-enough-123456"
	cfg.UploadDir = t.TempDir()
	cfg.UploadDirPath = cfg.UploadDir
	cfg.LogDir = t.TempDir()
	cfg.LogDirPath = cfg.LogDir
	cfg.TemplateDir = t.TempDir()
	cfg.WechatMiniProgramAppID = "wx-test-primary,wx-test-secondary"
	cfg.WechatMiniProgramAppSecret = "test-primary-secret,test-secondary-secret"
	cfg.CORSOrigins = nil
	return cfg
}

// AllModels 全部表（AutoMigrate 顺序）。
func AllModels() []any {
	return []any{
		&models.User{}, &models.MiniProgramUser{}, &models.MiniProgramIdentity{},
		&models.BusinessEventLog{}, &models.SystemSetting{},
		&models.WebhookChannel{}, &models.WebhookDelivery{},
		&models.FileObject{}, &models.MaterialCodeLibrary{},
		&models.ExcelImportJob{}, &models.ExcelExportJob{}, &models.ShareLink{},
		&models.HuaXingInventory{}, &models.LiteInventory{},
		&models.PurchaseRequest{}, &models.StockMaterial{}, &models.StockBalance{},
		&models.StockMaterialImage{}, &models.StockReplenishmentPolicy{},
		&models.PurchaseMaterial{}, &models.PurchaseMaterialImage{},
		&models.PurchasePlanTemplate{}, &models.PurchasePlanTemplateImage{},
		&models.PurchaseRequestLine{}, &models.PurchaseRequestLineImage{},
		&models.StockOperation{}, &models.StockOperationLine{},
	}
}

// OpenTestDB 打开内存 SQLite 并按模型建表。
func OpenTestDB(t *testing.T, cfg *config.Config) *gorm.DB {
	t.Helper()
	db, closeFn, err := database.Open(cfg)
	if err != nil {
		t.Fatalf("打开测试 DB 失败: %v", err)
	}
	t.Cleanup(closeFn)
	if err := db.AutoMigrate(AllModels()...); err != nil {
		t.Fatalf("AutoMigrate 失败: %v", err)
	}
	return db
}

// SeedUsers 写入四个角色账号（密码 123456）。
func SeedUsers(t *testing.T, db *gorm.DB) {
	t.Helper()
	hash, err := security.HashPassword("123456")
	if err != nil {
		t.Fatalf("HashPassword: %v", err)
	}
	users := []models.User{
		{Username: "admin", PasswordHash: hash, APITokenHash: security.HashAPIToken("00000000-0000-4000-8000-000000000001"), DisplayName: "系统管理员", Role: "SUPER_ADMIN", Enabled: true},
		{Username: "warehouse", PasswordHash: hash, APITokenHash: security.HashAPIToken("00000000-0000-4000-8000-000000000002"), DisplayName: "仓库管理员", Role: "WAREHOUSE_ADMIN", Enabled: true},
		{Username: "purchase", PasswordHash: hash, APITokenHash: security.HashAPIToken("00000000-0000-4000-8000-000000000003"), DisplayName: "申购管理员", Role: "PURCHASE_ADMIN", Enabled: true},
		{Username: "readonly", PasswordHash: hash, APITokenHash: security.HashAPIToken("00000000-0000-4000-8000-000000000004"), DisplayName: "只读用户", Role: "READ_ONLY", Enabled: true},
	}
	if err := db.Create(&users).Error; err != nil {
		t.Fatalf("种子用户失败: %v", err)
	}
}

// TestServer 返回已配置的 Gin engine。
func TestServer(t *testing.T, cfg *config.Config, db *gorm.DB) *gin.Engine {
	t.Helper()
	gin.SetMode(gin.TestMode)
	app := handler.NewApp(cfg, db)
	r := router.New(app)
	router.RegisterAPI(r, app)
	return r
}

// Do 执行请求并返回 recorder。
func Do(t *testing.T, r *gin.Engine, method, path string, headers map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, path, nil)
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}
