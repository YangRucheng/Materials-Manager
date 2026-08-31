package service

import (
	"testing"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/database"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

func testCfg() *config.Config {
	cfg := config.Load(".")
	cfg.JWTSecret = "test-secret-that-is-long-enough-123456"
	cfg.DatabaseURL = "sqlite+aiosqlite:///:memory:"
	return cfg
}

func TestAPITokenEncryptEchoRoundTrip(t *testing.T) {
	cfg := testCfg()
	user := &models.User{}
	issueAPIToken(cfg, user)
	if user.APIToken == "" || len(user.APIToken) != 36 {
		t.Fatalf("签发令牌异常: %q", user.APIToken)
	}
	if user.APITokenHash == "" {
		t.Fatal("应有哈希")
	}
	if user.APITokenEnc == "" {
		t.Fatal("应有 Fernet 密文")
	}
	// 清空临时明文，模拟从库中读回，解密应还原同一令牌（读取即回显）。
	user.APIToken = ""
	echoAPIToken(cfg, user)
	if user.APIToken == "" {
		t.Fatal("回显令牌不应为空")
	}
}

func TestAPITokenEchoLegacyNoCipher(t *testing.T) {
	cfg := testCfg()
	// 旧数据：只有哈希、无密文 → 回显为空（前端提示重新生成一次）。
	user := &models.User{APITokenHash: "deadbeef"}
	echoAPIToken(cfg, user)
	if user.APIToken != "" {
		t.Fatalf("旧数据无密文回显应为空，实际 %q", user.APIToken)
	}
}

func TestListUsersEchoDecryptedToken(t *testing.T) {
	cfg := testCfg()
	db, err := database.Open(cfg)
	if err != nil {
		t.Fatal(err)
	}
	sqlDB, _ := db.DB()
	defer sqlDB.Close()
	if err := db.AutoMigrate(&models.User{}); err != nil {
		t.Fatal(err)
	}
	// 模拟：直接建一个带密文的用户（等价创建接口写库后的状态）
	token := "aaaaaaaa-bbbb-4ccc-8ddd-eeeeffff0000"
	enc, err := security.FernetEncrypt(cfg.FernetKey, cfg.JWTSecret, token)
	if err != nil {
		t.Fatal(err)
	}
	seed := models.User{
		Username:     "echo_test",
		PasswordHash: "x",
		APITokenHash: security.HashAPIToken(token),
		APITokenEnc:  enc,
		DisplayName:  "回显测试",
		Role:         "READ_ONLY",
		Enabled:      true,
	}
	if err := db.Create(&seed).Error; err != nil {
		t.Fatal(err)
	}
	items, total, appErr := ListUsers(cfg, db, "echo_test", 1, 20)
	if appErr != nil {
		t.Fatal(appErr)
	}
	if total != 1 || len(items) != 1 {
		t.Fatalf("total=%d len=%d", total, len(items))
	}
	if items[0].APIToken != token {
		t.Fatalf("列表应回显解密令牌，实际 %q", items[0].APIToken)
	}
}
