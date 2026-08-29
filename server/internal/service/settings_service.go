package service

import (
	"encoding/json"

	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/models"
)

// 系统设置常量（与 ai_search_service 一致）。
const (
	SettingKeyAI         = "ai_search_config"
	SettingBusinessType  = "SYSTEM_SETTING"
	SettingBusinessID    = 1
	SettingActionUpdated = "AI_SEARCH_CONFIG_UPDATED"
)

// GetSettingData 读取 ai_search_config 配置字典；无表行时回退读取最后一条配置审计事件。
func GetSettingData(db *gorm.DB) map[string]any {
	var row models.SystemSetting
	if err := db.Where("setting_key = ?", SettingKeyAI).First(&row).Error; err == nil {
		var data map[string]any
		if err := json.Unmarshal(row.SettingValue, &data); err == nil {
			return data
		}
		return map[string]any{}
	}
	// 兼容旧部署：回退 business_event_log 最后一条 AI_SEARCH_CONFIG_UPDATED。
	var event models.BusinessEventLog
	err := db.Where("business_type = ? AND business_id = ? AND action = ?",
		SettingBusinessType, SettingBusinessID, SettingActionUpdated).
		Order("id DESC").First(&event).Error
	if err != nil {
		return nil
	}
	var data map[string]any
	if err := json.Unmarshal(event.AfterData, &data); err != nil {
		return nil
	}
	return data
}

// Str 读取配置中的字符串字段。
func SettingStr(data map[string]any, key, def string) string {
	if data == nil {
		return def
	}
	if v, ok := data[key].(string); ok {
		return v
	}
	return def
}

// Bool 读取配置中的布尔字段。
func SettingBool(data map[string]any, key string, def bool) bool {
	if data == nil {
		return def
	}
	if v, ok := data[key].(bool); ok {
		return v
	}
	return def
}

// IsLiteSecondaryWarehouse 二级库是否精简模式（独立表 + 只读 + Excel 导入）。
func IsLiteSecondaryWarehouse(db *gorm.DB) bool {
	data := GetSettingData(db)
	return SettingStr(data, "secondary_warehouse_mode", "") == "lite"
}
