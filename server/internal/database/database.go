// Package database 建立 GORM 连接（MySQL 生产 / SQLite 测试），
// 与原 Python 实现（backend/app/core/database.py）语义对齐。
package database

import (
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/glebarez/sqlite"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/yangrucheng/materials-manager/server/internal/config"
)

// Open 根据配置的 database_url 打开 GORM 连接。
// 返回 db、close 函数。SQLite 内存库由调用方决定是否 AutoMigrate/建表。
func Open(cfg *config.Config) (*gorm.DB, func(), error) {
	if dsn, ok := config.SQLitePath(cfg.DatabaseURL); ok {
		return openSQLite(dsn)
	}
	dsn, ok := config.MySQLDSN(cfg.DatabaseURL)
	if !ok {
		return nil, nil, fmt.Errorf("不支持的数据库 URL: %s", cfg.DatabaseURL)
	}
	return openMySQL(dsn)
}

func openMySQL(dsn string) (*gorm.DB, func(), error) {
	sqlDB, err := gorm.Open(mysql.Open(dsn), &gorm.Config{
		Logger: gormLogger(),
	})
	if err != nil {
		return nil, nil, fmt.Errorf("连接 MySQL 失败: %w", err)
	}
	raw, err := sqlDB.DB()
	if err != nil {
		return nil, nil, err
	}
	// pool_pre_ping 等价：连接池配置 + 惰性验证。
	raw.SetMaxOpenConns(20)
	raw.SetMaxIdleConns(10)
	raw.SetConnMaxLifetime(30 * time.Minute)
	return sqlDB, func() { _ = raw.Close() }, nil
}

func openSQLite(dsn string) (*gorm.DB, func(), error) {
	sqlDB, err := gorm.Open(sqlite.Open(dsn), &gorm.Config{
		Logger: gormLogger(),
	})
	if err != nil {
		return nil, nil, fmt.Errorf("连接 SQLite 失败: %w", err)
	}
	raw, err := sqlDB.DB()
	if err != nil {
		return nil, nil, err
	}
	raw.SetMaxOpenConns(1)
	return sqlDB, func() { _ = raw.Close() }, nil
}

func gormLogger() logger.Interface {
	return logger.New(slog.NewLogLogger(slog.Default().Handler(), slog.LevelInfo), logger.Config{
		SlowThreshold:             500 * time.Millisecond,
		LogLevel:                  logger.Warn,
		IgnoreRecordNotFoundError: true,
		Colorful:                  false,
	})
}

// IsMySQL 判断当前连接方言是否为 MySQL（用于 SQL 分支）。
func IsMySQL(db *gorm.DB) bool {
	return strings.Contains(strings.ToLower(db.Dialector.Name()), "mysql")
}

// IsSQLite 判断当前连接方言是否为 SQLite。
func IsSQLite(db *gorm.DB) bool {
	return strings.Contains(strings.ToLower(db.Dialector.Name()), "sqlite")
}
