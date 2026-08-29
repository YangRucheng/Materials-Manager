// Package logging 配置 log/slog：控制台 + 每日轮转文件（保留份数可配）。
// 日志格式非 API 契约，与 Python 后端仅需语义等价。
package logging

import (
	"log/slog"
	"os"
	"path/filepath"

	"gopkg.in/natefinch/lumberjack.v2"
)

// Configure 初始化根 logger（控制台 + 文件双输出）。
func Configure(logDir string, backupCount int) {
	if backupCount <= 0 {
		backupCount = 90
	}
	fileWriter := &lumberjack.Logger{
		Filename:   filepath.Join(logDir, "spare-parts-api.log"),
		MaxSize:    100, // MB
		MaxBackups: backupCount,
		MaxAge:     365,
		LocalTime:  true,
		Compress:   false,
	}
	consoleHandler := slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	})
	fileHandler := slog.NewTextHandler(fileWriter, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	})
	root := slog.New(slog.NewMultiHandler(consoleHandler, fileHandler))
	slog.SetDefault(root)
}
