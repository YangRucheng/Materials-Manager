package service

import (
	"encoding/json"

	"github.com/google/uuid"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/database"
	"github.com/yangrucheng/materials-manager/server/internal/domain"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
)

// LogOperationEvent 写入库存流水审计日志（business_event_log）。
func LogOperationEvent(tx *gorm.DB, item *models.StockOperation, action string, before map[string]any) *apperrors.AppError {
	after := operationSnapshot(item)
	event := models.BusinessEventLog{
		BusinessType: "STOCK_OPERATION",
		BusinessID:   item.ID,
		Action:       action,
		OccurredAt:   models.UTCNow(),
	}
	if before != nil {
		event.BeforeData = mustJSON(before)
	}
	event.AfterData = mustJSON(after)
	if err := tx.Create(&event).Error; err != nil {
		return database.MapDBError(err)
	}
	return nil
}

// EnqueueWebhookEvent 为订阅了该事件的启用渠道登记投递行（投递 worker 在 P8）。
func EnqueueWebhookEvent(tx *gorm.DB, eventType string, payload map[string]any) {
	var channels []models.WebhookChannel
	if err := tx.Where("enabled = ?", true).Find(&channels).Error; err != nil {
		return
	}
	eventID := uuid.New().String()
	for _, ch := range channels {
		var subscribed []string
		_ = json.Unmarshal(ch.SubscribedEvents, &subscribed)
		if !containsString(subscribed, eventType) {
			continue
		}
		delivery := models.WebhookDelivery{
			EventID:     eventID,
			EventType:   eventType,
			ChannelID:   ch.ID,
			Payload:     mustJSON(payload),
			Status:      domain.WebhookPending,
			NextRetryAt: models.UTCNow(),
			CreatedAt:   models.UTCNow(),
			UpdatedAt:   models.UTCNow(),
		}
		_ = tx.Create(&delivery).Error
	}
}

func containsString(list []string, target string) bool {
	for _, s := range list {
		if s == target {
			return true
		}
	}
	return false
}

func mustJSON(v any) models.JSON {
	data, err := json.Marshal(v)
	if err != nil {
		return models.JSON("{}")
	}
	return models.JSON(data)
}
