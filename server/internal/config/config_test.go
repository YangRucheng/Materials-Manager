package config_test

import (
	"testing"

	"github.com/yangrucheng/materials-manager/server/internal/config"
)

func TestMySQLDSNConversion(t *testing.T) {
	dsn, ok := config.MySQLDSN("mysql+asyncmy://root:root@127.0.0.1:3306/spare_parts?charset=utf8mb4")
	if !ok {
		t.Fatal("应识别 mysql+asyncmy URL")
	}
	want := "root:root@tcp(127.0.0.1:3306)/spare_parts?charset=utf8mb4&loc=UTC&parseTime=true"
	got := dsn
	if got != want {
		t.Fatalf("DSN 转换不符\n got=%q\nwant=%q", got, want)
	}
}

func TestSQLiteDetection(t *testing.T) {
	if _, ok := config.SQLitePath("sqlite+aiosqlite:///:memory:"); !ok {
		t.Fatal("应识别 SQLite 内存 URL")
	}
	if path, ok := config.SQLitePath("sqlite+aiosqlite:////tmp/test.db"); !ok || path != "/tmp/test.db" {
		t.Fatalf("SQLite 文件路径解析失败: %q", path)
	}
	if _, ok := config.SQLitePath("mysql+asyncmy://x"); ok {
		t.Fatal("MySQL URL 不应被识别为 SQLite")
	}
}

func TestCORSOriginsParse(t *testing.T) {
	t.Setenv("APP_CORS_ORIGINS", "https://app.example.com, .example.com, ")
	cfg := config.Load(".")
	if len(cfg.CORSOrigins) != 2 {
		t.Fatalf("CORSOrigins=%v", cfg.CORSOrigins)
	}
	if cfg.CORSOrigins[0] != "https://app.example.com" || cfg.CORSOrigins[1] != ".example.com" {
		t.Fatalf("CORSOrigins 解析错误: %v", cfg.CORSOrigins)
	}
}
