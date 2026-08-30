// Package testutil 提供 Go 后端集成测试的共享设施：
// SQLite 内存（默认，按模型建表）或 MySQL（TEST_DATABASE_URL 时：每测试独立库 + init.sql 建表）
// + 种子账号 + httptest 客户端。
package testutil

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/glebarez/sqlite"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/handler"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/router"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

// TestDatabaseURL 环境变量：设置为 MySQL URL 时按 MySQL 方言跑测试。
const TestDatabaseURL = "TEST_DATABASE_URL"

// repoRoot 从当前工作目录向上查找仓库根目录（example/database/init.sql 所在目录）。
func repoRoot(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("获取工作目录失败: %v", err)
	}
	for i := 0; i < 6; i++ {
		if _, err := os.Stat(filepath.Join(dir, "example", "database", "init.sql")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	t.Fatalf("无法定位仓库根目录（example/database/init.sql 未找到）")
	return ""
}

// MySQLMode 是否启用 MySQL 测试模式。
func MySQLMode() bool {
	return os.Getenv(TestDatabaseURL) != ""
}

// NewTestConfig 构造测试配置（SQLite 内存或 TEST_DATABASE_URL，固定 JWT 密钥）。
func NewTestConfig(t *testing.T) *config.Config {
	t.Helper()
	cfg := config.Load(".")
	if u := os.Getenv(TestDatabaseURL); u != "" {
		cfg.DatabaseURL = u
	} else {
		cfg.DatabaseURL = "sqlite+aiosqlite:///:memory:"
	}
	cfg.JWTSecret = "test-secret-that-is-long-enough-123456"
	cfg.UploadDir = t.TempDir()
	cfg.UploadDirPath = cfg.UploadDir
	cfg.LogDir = t.TempDir()
	cfg.LogDirPath = cfg.LogDir
	cfg.TemplateDir = filepath.Join(repoRoot(t), "server", "templates")
	cfg.WechatMiniProgramAppID = "wx-test-primary,wx-test-secondary"
	cfg.WechatMiniProgramAppSecret = "test-primary-secret,test-secondary-secret"
	cfg.CORSOrigins = nil
	return cfg
}

// AllModels 全部表（AutoMigrate 顺序；SQLite 模式用）。
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

// OpenTestDB 打开测试 DB：
//   - SQLite（默认）：内存 + AutoMigrate
//   - MySQL（TEST_DATABASE_URL）：创建独立库 spare_parts_test_<rand>，执行 example/database/init.sql 建表，
//     测试结束 DROP DATABASE（隔离 + 生产同 schema）
func OpenTestDB(t *testing.T, cfg *config.Config) *gorm.DB {
	t.Helper()
	if MySQLMode() {
		return openMySQLIsolated(t, cfg)
	}
	// SQLite 内存：每测试独立库名，避免共享内存库造成跨测试数据污染
	name := "file:test_" + randomSuffix() + "?mode=memory&cache=shared"
	gormDB, err := gorm.Open(sqlite.Open(name), &gorm.Config{})
	if err != nil {
		t.Fatalf("打开 SQLite 失败: %v", err)
	}
	if err := gormDB.AutoMigrate(AllModels()...); err != nil {
		t.Fatalf("AutoMigrate 失败: %v", err)
	}
	return gormDB
}

// adminDSN 从测试 URL 提取无库名的管理连接 DSN（含 multiStatements 供 init.sql 使用）。
func adminDSN(testURL string) (string, error) {
	base := strings.TrimPrefix(testURL, "mysql+asyncmy://")
	if base == testURL {
		base = strings.TrimPrefix(testURL, "mysql://")
	}
	if base == testURL {
		return "", fmt.Errorf("非 MySQL 测试 URL: %s", testURL)
	}
	beforeQuery, _, _ := strings.Cut(base, "?")
	at := strings.LastIndex(beforeQuery, "@")
	var creds, hostDB string
	if at >= 0 {
		creds = beforeQuery[:at]
		hostDB = beforeQuery[at+1:]
	} else {
		creds = ""
		hostDB = beforeQuery
	}
	host, _, _ := strings.Cut(hostDB, "/")
	return creds + "@tcp(" + host + ")/?parseTime=true&loc=UTC&multiStatements=true&charset=utf8mb4", nil
}

func randomSuffix() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func openMySQLIsolated(t *testing.T, cfg *config.Config) *gorm.DB {
	t.Helper()
	dsn, err := adminDSN(cfg.DatabaseURL)
	if err != nil {
		t.Fatalf("解析 MySQL 测试 URL 失败: %v", err)
	}
	admin, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatalf("连接 MySQL 管理连接失败: %v", err)
	}
	adminSQL, _ := admin.DB()
	dbName := "spare_parts_test_" + randomSuffix()
	if _, err := adminSQL.Exec("CREATE DATABASE " + dbName + " CHARACTER SET utf8mb4"); err != nil {
		_ = adminSQL.Close()
		t.Fatalf("创建测试库失败: %v", err)
	}
	// 在测试库上执行 init.sql
	initSQL, err := os.ReadFile(filepath.Join(repoRoot(t), "example", "database", "init.sql"))
	if err != nil {
		_ = adminSQL.Close()
		t.Fatalf("读取 init.sql 失败: %v", err)
	}
	if _, err := adminSQL.Exec("USE " + dbName); err != nil {
		_ = adminSQL.Close()
		t.Fatalf("USE 测试库失败: %v", err)
	}
	if _, err := adminSQL.Exec(string(initSQL)); err != nil {
		_ = adminSQL.Close()
		t.Fatalf("执行 init.sql 失败: %v", err)
	}
	_ = adminSQL.Close()

	// 打开测试库连接
	testDSN := buildTestDSN(cfg.DatabaseURL, dbName)
	gormDB, err := gorm.Open(mysql.Open(testDSN), &gorm.Config{})
	if err != nil {
		t.Fatalf("连接测试库失败: %v", err)
	}
	raw, _ := gormDB.DB()
	t.Cleanup(func() {
		// 关闭连接后删除测试库
		_ = raw.Close()
		admin2, err2 := gorm.Open(mysql.Open(dsn), &gorm.Config{})
		if err2 == nil {
			sqlDB2, _ := admin2.DB()
			_, _ = sqlDB2.Exec("DROP DATABASE IF EXISTS " + dbName)
			_ = sqlDB2.Close()
		}
	})
	return gormDB
}

// buildTestDSN 拼出指向指定库的 DSN（参数固定，避免与原始 URL 参数重复）。
func buildTestDSN(testURL, dbName string) string {
	base := strings.TrimPrefix(testURL, "mysql+asyncmy://")
	if base == testURL {
		base = strings.TrimPrefix(testURL, "mysql://")
	}
	beforeQuery, _, _ := strings.Cut(base, "?")
	at := strings.LastIndex(beforeQuery, "@")
	hostDB := beforeQuery
	if at >= 0 {
		hostDB = beforeQuery[at+1:]
	}
	host, _, _ := strings.Cut(hostDB, "/")
	creds := ""
	if at >= 0 {
		creds = beforeQuery[:at]
	}
	return creds + "@tcp(" + host + ")/" + dbName + "?parseTime=true&loc=UTC&charset=utf8mb4"
}

// SeedUsers 写入四个角色账号（密码 123456）；MySQL 模式 init.sql 已种入则跳过。
func SeedUsers(t *testing.T, db *gorm.DB) {
	t.Helper()
	var count int64
	db.Model(&models.User{}).Where("username = ?", "admin").Count(&count)
	if count > 0 {
		return
	}
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
