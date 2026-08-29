package service

import (
	"encoding/json"
	"time"
	"net/http"
	"strings"

	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/aiclient"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

// AISettings AI 搜索配置（读模型）。
type AISettings struct {
	Endpoint    string
	APIKey      string
	Model       string
	Enabled     bool
	MiniProgramCodeEnv    string
	MiniProgramCodeAppID  string
	MiniProgramAppIDs     []string
	RegistrationEnabled   bool
	NewUserEnabled        bool
	ImageAccelerationURL  string
	InventoryMode         string
	HuaXingInventoryMode  string
	PurchasePlansMode     string
	PurchaseRecordsMode   string
	MaterialCodesMode     string
	SecondaryWarehouseMode string
	UpdatedAt             *time.Time
	Version               int
}

// AISettingsRead 读取 AI 配置（含解密明文 api_key）。
func AISettingsRead(cfg *config.Config, db *gorm.DB) *AISettings {
	data := GetSettingData(db)
	return configFromData(cfg, data, versionOf(db, data), nil)
}

func versionOf(db *gorm.DB, data map[string]any) int {
	var row models.SystemSetting
	if err := db.Where("setting_key = ?", SettingKeyAI).First(&row).Error; err == nil {
		return row.Version
	}
	var event models.BusinessEventLog
	if err := db.Where("business_type = ? AND business_id = ? AND action = ?",
		SettingBusinessType, SettingBusinessID, SettingActionUpdated).
		Order("id DESC").First(&event).Error; err == nil {
		return int(event.ID)
	}
	return 0
}

func configFromData(cfg *config.Config, data map[string]any, version int, updatedAt *time.Time) *AISettings {
	endpoint := ""
	if v, ok := data["endpoint"].(string); ok {
		endpoint = v
	}
	apiKeyEncrypted := ""
	if v, ok := data["api_key_encrypted"].(string); ok {
		apiKeyEncrypted = v
	}
	model := ""
	if v, ok := data["model"].(string); ok {
		model = v
	}
	enabled := false
	if v, ok := data["enabled"].(bool); ok {
		enabled = v
	}
	apiKey := ""
	if apiKeyEncrypted != "" {
		if plain, err := security.FernetDecrypt(cfg.FernetKey, cfg.JWTSecret, apiKeyEncrypted); err == nil {
			apiKey = plain
		}
	}
	appIDs := splitNonEmpty(cfg.WechatMiniProgramAppID)
	return &AISettings{
		Endpoint: endpoint, APIKey: apiKey, Model: model, Enabled: enabled,
		MiniProgramCodeEnv:   settingStrDefault(data, "mini_program_code_env", "release"),
		MiniProgramCodeAppID: settingStrDefault(data, "mini_program_code_app_id", ""),
		MiniProgramAppIDs:    appIDs,
		RegistrationEnabled:  settingBoolDefault(data, "mini_program_registration_enabled", true),
		NewUserEnabled:       settingBoolDefault(data, "mini_program_new_user_enabled", true),
		ImageAccelerationURL: settingStrDefault(data, "image_acceleration_server_url", ""),
		InventoryMode:        settingStrDefault(data, "inventory_mode", "read_write"),
		HuaXingInventoryMode: settingStrDefault(data, "huaxing_inventory_mode", "query_only"),
		PurchasePlansMode:    settingStrDefault(data, "purchase_plans_mode", "query_only"),
		PurchaseRecordsMode:  settingStrDefault(data, "purchase_records_mode", "query_only"),
		MaterialCodesMode:    settingStrDefault(data, "material_codes_mode", "query_only"),
		SecondaryWarehouseMode: settingStrDefault(data, "secondary_warehouse_mode", "full"),
		Version:              version,
	}
}

func settingStrDefault(data map[string]any, key, def string) string {
	if v, ok := data[key].(string); ok {
		return v
	}
	return def
}

func settingBoolDefault(data map[string]any, key string, def bool) bool {
	if v, ok := data[key].(bool); ok {
		return v
	}
	return def
}

// UpdateAISettings 更新 AI 配置（乐观锁 + 审计）。
func UpdateAISettings(cfg *config.Config, db *gorm.DB, version int, endpoint, apiKey, model string, enabled bool, env, appID string, registrationEnabled, newUserEnabled bool, imageURL string, inventoryMode, huaXingMode, plansMode, recordsMode, codesMode, warehouseMode string) *apperrors.AppError {
	var row models.SystemSetting
	found := db.Where("setting_key = ?", SettingKeyAI).First(&row).Error == nil
	if found && version != 0 && version != row.Version {
		return apperrors.VersionConflict(version, row.Version)
	}
	data := GetSettingData(db)
	if data == nil {
		data = map[string]any{}
	}
	apiKeyEncrypted := settingStrDefault(data, "api_key_encrypted", "")
	if apiKey != "" {
		enc, err := security.FernetEncrypt(cfg.FernetKey, cfg.JWTSecret, apiKey)
		if err == nil {
			apiKeyEncrypted = enc
		}
	}
	newData := map[string]any{
		"endpoint": endpoint, "api_key_encrypted": apiKeyEncrypted, "model": model, "enabled": enabled,
		"mini_program_code_env": env, "mini_program_code_app_id": appID,
		"mini_program_registration_enabled": registrationEnabled,
		"mini_program_new_user_enabled":     newUserEnabled,
		"image_acceleration_server_url":     imageURL,
		"inventory_mode": inventoryMode, "huaxing_inventory_mode": huaXingMode,
		"purchase_plans_mode": plansMode, "purchase_records_mode": recordsMode,
		"material_codes_mode": codesMode, "secondary_warehouse_mode": warehouseMode,
	}
	raw, _ := json.Marshal(newData)
	now := models.UTCNow()
	if found {
		newVersion := row.Version + 1
		if err := db.Model(&models.SystemSetting{}).Where("setting_key = ?", SettingKeyAI).
			Updates(map[string]any{"setting_value": models.JSON(raw), "version": gorm.Expr("version + 1"), "updated_at": now}).Error; err != nil {
			return DatabaseError(err)
		}
		_ = newVersion
	} else {
		if err := db.Create(&models.SystemSetting{
			SettingKey: SettingKeyAI, SettingValue: models.JSON(raw), Version: 1, UpdatedAt: now,
		}).Error; err != nil {
			return DatabaseError(err)
		}
	}
	// 审计
	action := "AI_SEARCH_CONFIG_UPDATED"
	if !enabled {
		action = "AI_SEARCH_CONFIG_DISABLED"
	}
	_ = db.Create(&models.BusinessEventLog{
		BusinessType: SettingBusinessType, BusinessID: SettingBusinessID, Action: action,
		AfterData: models.JSON(raw), OccurredAt: now,
	}).Error
	return nil
}

// ExpandSearchValue 非严格扩词：失败静默返回原词。
func ExpandSearchValue(cfg *config.Config, db *gorm.DB, value string) string {
	if value == "" {
		return value
	}
	settings := AISettingsRead(cfg, db)
	if !settings.Enabled || settings.APIKey == "" || settings.Endpoint == "" {
		return value
	}
	terms := SplitOrSearchTerms(value)
	if len(terms) == 0 {
		return value
	}
	var expanded []string
	for _, term := range terms {
		expanded = append(expanded, term)
		syns, err := aiclient.Expand(aiclient.ExpandRequest{
			Endpoint: settings.Endpoint, APIKey: settings.APIKey,
			Model: settings.Model, Value: term,
		})
		if err == nil {
			expanded = append(expanded, syns...)
		}
	}
	// 去重拼接
	seen := map[string]bool{}
	var out []string
	for _, term := range expanded {
		trimmed := strings.TrimSpace(term)
		if trimmed != "" && !seen[trimmed] {
			seen[trimmed] = true
			out = append(out, trimmed)
		}
	}
	return strings.Join(out, "|")
}

// ExpandStrict 严格扩词（失败抛错）。
func ExpandStrict(cfg *config.Config, db *gorm.DB, value string) (string, *apperrors.AppError) {
	settings := AISettingsRead(cfg, db)
	if !settings.Enabled || settings.APIKey == "" {
		return "", apperrors.New("AI_NOT_CONFIGURED", "AI 搜索尚未配置", http.StatusServiceUnavailable, nil)
	}
	if settings.Endpoint == "" {
		return "", apperrors.New("AI_NOT_CONFIGURED", "AI 搜索尚未配置", http.StatusServiceUnavailable, nil)
	}
	decrypted := ""
	if settings.APIKey != "" {
		decrypted = settings.APIKey
	}
	syns, err := aiclient.Expand(aiclient.ExpandRequest{
		Endpoint: settings.Endpoint, APIKey: decrypted, Model: settings.Model, Value: value,
	})
	if err != nil {
		code := err.Error()
		status := 400
		switch code {
		case "AI_RATE_LIMITED":
			status = 429
		case "AI_UPSTREAM_FAILED":
			status = 502
		case "AI_INVALID_RESPONSE":
			status = 502
		}
		return "", apperrors.New(code, aiMessage(code), status, nil)
	}
	seen := map[string]bool{}
	var out []string
	for _, s := range syns {
		if !seen[s] {
			seen[s] = true
			out = append(out, s)
		}
	}
	return strings.Join(out, "|"), nil
}

func aiMessage(code string) string {
	switch code {
	case "AI_AUTH_FAILED":
		return "AI 接口认证失败，请检查 API Key"
	case "AI_ENDPOINT_NOT_FOUND":
		return "AI 接口地址不存在"
	case "AI_RATE_LIMITED":
		return "AI 接口请求过于频繁，请稍后再试"
	case "AI_UPSTREAM_FAILED":
		return "AI 服务暂不可用，请稍后再试"
	case "AI_INVALID_RESPONSE":
		return "AI 服务返回异常"
	case "AI_RESPONSE_TIMEOUT":
		return "AI 接口响应超时"
	case "AI_CONNECTION_FAILED":
		return "无法连接 AI 服务"
	default:
		return "AI 搜索失败"
	}
}

// TestAISettings 测试配置（固定"电机"，30s 超时）。
func TestAISettings(endpoint, apiKey, model string) *apperrors.AppError {
	if endpoint == "" || apiKey == "" || model == "" {
		return apperrors.New("AI_NOT_CONFIGURED", "AI 搜索尚未配置", http.StatusServiceUnavailable, nil)
	}
	_, err := aiclient.Expand(aiclient.ExpandRequest{
		Endpoint: endpoint, APIKey: apiKey, Model: model, Value: "电机", Test: true,
	})
	if err != nil {
		code := err.Error()
		status := 400
		if code == "AI_RATE_LIMITED" {
			status = 429
		}
		return apperrors.New(code, aiMessage(code), status, nil)
	}
	return nil
}
