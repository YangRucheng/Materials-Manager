package security_test

import (
	"testing"
	"time"

	"github.com/yangrucheng/materials-manager/server/internal/security"
)

const (
	testJWTSecret   = "e2e-test-secret-that-is-long-enough-123456"
	knownArgon2Hash = "$argon2id$v=19$m=65536,t=3,p=4$VNlqfY9XSeszkV1Ry0SIiQ$/ll+8yljB5zZ/oCnO9cj+dzh4p05nebxSdxy1icYrKg"
	pythonFernetTok = "gAAAAABqksvzHXCn42DNAB8YhXnvrpi28YhLGAzBgt3z4sib9INUjku1TXlCjnhOZIUUsKVoA5OvAB9QG6-Cz9HOXErwc92lVQ=="
)

// 校验 init.sql 中的 argon2-cffi 哈希（密码 123456）能被 Go 验证。
func TestVerifyArgon2Compat(t *testing.T) {
	if !security.VerifyPassword(knownArgon2Hash, "123456") {
		t.Fatal("argon2-cffi 哈希校验失败")
	}
	if security.VerifyPassword(knownArgon2Hash, "wrong") {
		t.Fatal("错误密码不应通过")
	}
}

// Go 生成的哈希可自校验。
func TestHashRoundTrip(t *testing.T) {
	hash, err := security.HashPassword("123456")
	if err != nil {
		t.Fatal(err)
	}
	if !security.VerifyPassword(hash, "123456") {
		t.Fatal("自生成哈希校验失败")
	}
	if security.VerifyPassword(hash, "1234567") {
		t.Fatal("错误密码不应通过")
	}
}

// Fernet：Python cryptography 生成的密文可被 Go 解密；Go 加密的密文可再解密。
func TestFernetCompat(t *testing.T) {
	plain, err := security.FernetDecrypt("", testJWTSecret, pythonFernetTok)
	if err != nil {
		t.Fatalf("解密 Python Fernet 密文失败: %v", err)
	}
	if plain != "hello-fernet" {
		t.Fatalf("解密内容不符: %q", plain)
	}

	enc, err := security.FernetEncrypt("", testJWTSecret, "webhook-secret-1")
	if err != nil {
		t.Fatal(err)
	}
	back, err := security.FernetDecrypt("", testJWTSecret, enc)
	if err != nil {
		t.Fatal(err)
	}
	if back != "webhook-secret-1" {
		t.Fatal("Fernet 往返不一致")
	}

	// 独立密钥优先：配置 APP_FERNET_KEY 后仍可解旧 jwt_secret 派生密文。
	plain2, err := security.FernetDecrypt("independent-fernet-key-1234567890", testJWTSecret, pythonFernetTok)
	if err != nil {
		t.Fatalf("独立密钥回退失败: %v", err)
	}
	if plain2 != "hello-fernet" {
		t.Fatal("回退解密内容不符")
	}
}

func TestJWT(t *testing.T) {
	access, err := security.NewAccessToken(testJWTSecret, "HS256", 42, 30*time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	claims, err := security.DecodeToken(testJWTSecret, "HS256", access)
	if err != nil {
		t.Fatal(err)
	}
	if claims.Subject != "42" || claims.TokenType != "management_access" || claims.ID == "" {
		t.Fatalf("claims 不符: %+v", claims)
	}

	// 篡改令牌应失败
	if _, err := security.DecodeToken(testJWTSecret, "HS256", access[:len(access)-2]+"xx"); err == nil {
		t.Fatal("篡改令牌不应通过")
	}

	refresh, err := security.NewRefreshToken(testJWTSecret, "HS256", 7, 3, 7*24*time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	rClaims, err := security.DecodeToken(testJWTSecret, "HS256", refresh)
	if err != nil {
		t.Fatal(err)
	}
	if rClaims.TokenType != "management_refresh" || rClaims.Version == nil || *rClaims.Version != 3 {
		t.Fatalf("refresh claims 不符: %+v", rClaims)
	}
}

func TestAPITokenHash(t *testing.T) {
	token := "550e8400-e29b-41d4-a716-446655440000"
	h := security.HashAPIToken(token)
	if len(h) != 64 {
		t.Fatalf("哈希长度不符: %d", len(h))
	}
	if security.HashAPIToken(token) != h {
		t.Fatal("哈希不稳定")
	}
}
