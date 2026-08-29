// Package main 后端入口。
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/database"
	"github.com/yangrucheng/materials-manager/server/internal/handler"
	"github.com/yangrucheng/materials-manager/server/internal/logging"
	"github.com/yangrucheng/materials-manager/server/internal/router"
)

func main() {
	// 工作目录：优先取 /app（容器），否则二进制所在目录。
	rootDir := os.Getenv("APP_ROOT_DIR")
	if rootDir == "" {
		if cwd, err := os.Getwd(); err == nil {
			rootDir = cwd
		} else {
			rootDir = "."
		}
	}
	cfg := config.Load(rootDir)

	if err := os.MkdirAll(cfg.UploadDirPath, 0o755); err != nil {
		slog.Error("创建上传目录失败", "error", err)
		os.Exit(1)
	}
	if err := os.MkdirAll(cfg.LogDirPath, 0o755); err != nil {
		slog.Error("创建日志目录失败", "error", err)
		os.Exit(1)
	}
	logging.Configure(cfg.LogDirPath, cfg.LogBackupCount)
	slog.Info("service started", "environment", cfg.Environment, "log_dir", cfg.LogDirPath)

	db, closeDB, err := database.Open(cfg)
	if err != nil {
		slog.Error("数据库连接失败", "error", err)
		os.Exit(1)
	}
	defer closeDB()

	app := handler.NewApp(cfg, db)
	r := router.New(app)
	router.RegisterAPI(r, app)

	addr := "0.0.0.0:8000"
	if port := os.Getenv("APP_PORT"); port != "" {
		addr = "0.0.0.0:" + port
	}
	server := &http.Server{Addr: addr, Handler: r, ReadHeaderTimeout: 10 * time.Second}

	go func() {
		slog.Info("HTTP server listening", "addr", addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("HTTP server error", "error", err)
			os.Exit(1)
		}
	}()

	// 优雅停机
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	slog.Info("shutting down")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	_ = server.Shutdown(ctx)
}

var _ = filepath.Join
