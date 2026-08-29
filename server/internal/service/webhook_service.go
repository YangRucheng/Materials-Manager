package service

import (
	"bytes"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
	"github.com/yangrucheng/materials-manager/server/internal/webhook"
)

// EncryptWebhookSecret 加密 webhook 敏感字段。
func EncryptWebhookSecret(cfg *config.Config, value string) (string, error) {
	return security.FernetEncrypt(cfg.FernetKey, cfg.JWTSecret, value)
}

// DecryptWebhookSecret 解密 webhook 敏感字段。
func DecryptWebhookSecret(cfg *config.Config, value string) (string, error) {
	if value == "" {
		return "", nil
	}
	return security.FernetDecrypt(cfg.FernetKey, cfg.JWTSecret, value)
}

// VersionConflictErr 版本冲突错误。
func VersionConflictErr(expected, actual int) *apperrors.AppError {
	return apperrors.VersionConflict(expected, actual)
}

// MustJSONString 序列化为 JSON 字符串。
func MustJSONString(v any) string {
	data, _ := json.Marshal(v)
	return string(data)
}

// TestWebhook 发送测试消息。
func TestWebhook(cfg *config.Config, platform, webhookURL, secret string) *apperrors.AppError {
	p := webhook.PlatformFeishu
	if platform == "DINGTALK" {
		p = webhook.PlatformDingtalk
	}
	payload, signedURL, err := webhook.BuildPayload(p, webhookURL, secret, "测试", "这是一条测试消息")
	if err != nil {
		return apperrors.New("WEBHOOK_TEST_FAILED", "消息构造失败", 400, nil)
	}
	client := &http.Client{Timeout: 10 * time.Second}
	req, err := http.NewRequest("POST", signedURL, bytes.NewReader(payload))
	if err != nil {
		return apperrors.New("WEBHOOK_TEST_FAILED", "消息构造失败", 400, nil)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return apperrors.New("WEBHOOK_TEST_FAILED", "发送失败，请检查地址与网络", 400, nil)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return apperrors.New("WEBHOOK_TEST_FAILED", "发送失败，HTTP "+resp.Status, 400, nil)
	}
	return nil
}

// RunWebhookDeliveryWorker webhook 投递 worker（每 2s 轮询一次）。
func RunWebhookDeliveryWorker(cfg *config.Config, db *gorm.DB, stop <-chan struct{}) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-stop:
			return
		case <-ticker.C:
			deliverPendingOnce(cfg, db)
		}
	}
}

// deliverPendingOnce 领取并投递一条待发消息。
func deliverPendingOnce(cfg *config.Config, db *gorm.DB) {
	var delivery models.WebhookDelivery
	err := db.Where("status = ? AND next_retry_at <= ?", "PENDING", models.UTCNow()).
		Order("id").First(&delivery).Error
	if err != nil {
		// 租约恢复：SENDING 超 5min
		stale := models.UTCNow().Add(-5 * time.Minute)
		err = db.Where("status = ? AND updated_at <= ?", "SENDING", stale).
			Order("id").First(&delivery).Error
		if err != nil {
			return
		}
	}
	// 标记 SENDING + attempts+1
	attempts := delivery.Attempts + 1
	db.Model(&models.WebhookDelivery{}).Where("id = ?", delivery.ID).
		Updates(map[string]any{"status": "SENDING", "attempts": attempts, "updated_at": models.UTCNow()})

	var channel models.WebhookChannel
	if err := db.First(&channel, delivery.ChannelID).Error; err != nil {
		db.Model(&models.WebhookDelivery{}).Where("id = ?", delivery.ID).
			Updates(map[string]any{"status": "FAILED", "last_error": "渠道不存在", "updated_at": models.UTCNow()})
		return
	}
	url, _ := DecryptWebhookSecret(cfg, channel.WebhookURLEncrypted)
	secret, _ := DecryptWebhookSecret(cfg, channel.SecretEncrypted)
	var payload map[string]any
	_ = json.Unmarshal(delivery.Payload, &payload)
	p := webhook.PlatformFeishu
	if channel.Platform == "DINGTALK" {
		p = webhook.PlatformDingtalk
	}
	title, text := eventTitleText(payload)
	bodyBytes, signedURL, err := webhook.BuildPayload(p, url, secret, title, text)
	if err != nil {
		bodyBytes = []byte("{}")
		signedURL = url
	}
	client := &http.Client{Timeout: 10 * time.Second}
	req, _ := http.NewRequest("POST", signedURL, bytes.NewReader(bodyBytes))
	if req != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := client.Do(req)
	success := err == nil && resp != nil && resp.StatusCode >= 200 && resp.StatusCode < 300
	var excerpt string
	if resp != nil {
		excerpt = resp.Status
	}
	if success {
		now := models.UTCNow()
		db.Model(&models.WebhookDelivery{}).Where("id = ?", delivery.ID).
			Updates(map[string]any{"status": "SUCCEEDED", "delivered_at": now,
				"response_status": resp.StatusCode, "response_excerpt": truncateStr(excerpt, 1000),
				"updated_at": now})
		return
	}
	// 失败：重试退避
	if attempts >= 5 {
		db.Model(&models.WebhookDelivery{}).Where("id = ?", delivery.ID).
			Updates(map[string]any{"status": "FAILED", "last_error": truncateStr(errText(err, excerpt), 1000),
				"updated_at": models.UTCNow()})
		return
	}
	retryMinutes := []int{1, 5, 15, 60, 180}
	wait := time.Duration(retryMinutes[minInt(attempts-1, 4)]) * time.Minute
	db.Model(&models.WebhookDelivery{}).Where("id = ?", delivery.ID).
		Updates(map[string]any{"status": "PENDING", "next_retry_at": models.UTCNow().Add(wait),
			"last_error": truncateStr(errText(err, excerpt), 1000), "updated_at": models.UTCNow()})
}

func eventTitleText(payload map[string]any) (string, string) {
	eventType, _ := payload["event_type"].(string)
	switch eventType {
	case "stock.outbound.created":
		return "出库通知", describeStock(payload)
	case "stock.inbound.created":
		return "入库通知", describeStock(payload)
	case "mini_program.user.bound":
		return "小程序用户绑定", describeStock(payload)
	default:
		return "备件管理通知", "有新的业务事件"
	}
}

func describeStock(payload map[string]any) string {
	reason, _ := payload["business_reason"].(string)
	if reason == "" {
		reason = "库存变动"
	}
	if materials, ok := payload["materials"].([]any); ok && len(materials) > 0 {
		if m, ok := materials[0].(map[string]any); ok {
			name, _ := m["name"].(string)
			qty, _ := m["quantity"].(string)
			unit, _ := m["unit_name"].(string)
			return reason + "：" + name + " ×" + qty + unit
		}
	}
	return reason
}

func truncateStr(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max]
}

func errText(err error, fallback string) string {
	if err != nil {
		return err.Error()
	}
	return fallback
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

var _ = strings.TrimSpace
