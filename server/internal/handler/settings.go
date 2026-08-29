package handler

import (
	"net/http"
	"strings"

	"gorm.io/gorm"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// SettingsHandler AI 搜索 / 系统设置 / Webhook。
type SettingsHandler struct {
	App *App
}

func NewSettingsHandler(app *App) *SettingsHandler { return &SettingsHandler{App: app} }

// AIExpand POST /ai-search/expand
func (h *SettingsHandler) AIExpand(c *gin.Context) {
	var req struct {
		Value string `json:"value" binding:"required,max=500"`
	}
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	expanded, appErr := service.ExpandStrict(h.App.Cfg, h.App.DB, req.Value)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, map[string]any{"original": req.Value, "expanded": expanded})
}

// AIStatus GET /ai-search/status
func (h *SettingsHandler) AIStatus(c *gin.Context) {
	settings := service.AISettingsRead(h.App.Cfg, h.App.DB)
	respond.JSON(c, http.StatusOK, map[string]any{
		"available": settings.Enabled && settings.APIKey != "",
	})
}

// AIGetSettings GET /ai-search/settings（超管）
func (h *SettingsHandler) AIGetSettings(c *gin.Context) {
	settings := service.AISettingsRead(h.App.Cfg, h.App.DB)
	respond.JSON(c, http.StatusOK, map[string]any{
		"endpoint": settings.Endpoint, "api_key": settings.APIKey, "model": settings.Model,
		"enabled": settings.Enabled,
		"mini_program_code_env": settings.MiniProgramCodeEnv,
		"mini_program_code_app_id": settings.MiniProgramCodeAppID,
		"mini_program_app_ids": settings.MiniProgramAppIDs,
		"mini_program_registration_enabled": settings.RegistrationEnabled,
		"mini_program_new_user_enabled": settings.NewUserEnabled,
		"image_acceleration_server_url": settings.ImageAccelerationURL,
		"inventory_mode": settings.InventoryMode,
		"huaxing_inventory_mode": settings.HuaXingInventoryMode,
		"purchase_plans_mode": settings.PurchasePlansMode,
		"purchase_records_mode": settings.PurchaseRecordsMode,
		"material_codes_mode": settings.MaterialCodesMode,
		"secondary_warehouse_mode": settings.SecondaryWarehouseMode,
		"version": settings.Version,
	})
}

// AIUpdateSettings PUT /ai-search/settings（超管）
func (h *SettingsHandler) AIUpdateSettings(c *gin.Context) {
	var req struct {
		Endpoint          string `json:"endpoint"`
		APIKey            string `json:"api_key"`
		Model             string `json:"model"`
		Enabled           bool   `json:"enabled"`
		MiniProgramCodeEnv string `json:"mini_program_code_env"`
		MiniProgramCodeAppID string `json:"mini_program_code_app_id"`
		RegistrationEnabled bool `json:"mini_program_registration_enabled"`
		NewUserEnabled      bool `json:"mini_program_new_user_enabled"`
		ImageAccelerationServerURL string `json:"image_acceleration_server_url"`
		InventoryMode      string `json:"inventory_mode"`
		HuaXingInventoryMode string `json:"huaxing_inventory_mode"`
		PurchasePlansMode  string `json:"purchase_plans_mode"`
		PurchaseRecordsMode string `json:"purchase_records_mode"`
		MaterialCodesMode  string `json:"material_codes_mode"`
		SecondaryWarehouseMode string `json:"secondary_warehouse_mode"`
		Version            int `json:"version"`
	}
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if appErr := service.UpdateAISettings(h.App.Cfg, h.App.DB, req.Version, req.Endpoint, req.APIKey,
		req.Model, req.Enabled, req.MiniProgramCodeEnv, req.MiniProgramCodeAppID,
		req.RegistrationEnabled, req.NewUserEnabled, req.ImageAccelerationServerURL,
		req.InventoryMode, req.HuaXingInventoryMode, req.PurchasePlansMode,
		req.PurchaseRecordsMode, req.MaterialCodesMode, req.SecondaryWarehouseMode); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	settings := service.AISettingsRead(h.App.Cfg, h.App.DB)
	respond.JSON(c, http.StatusOK, map[string]any{
		"endpoint": settings.Endpoint, "api_key": settings.APIKey, "model": settings.Model,
		"enabled": settings.Enabled, "version": settings.Version,
	})
}

// AITest POST /ai-search/settings/test（超管）
func (h *SettingsHandler) AITest(c *gin.Context) {
	var req struct {
		Endpoint string `json:"endpoint"`
		APIKey   string `json:"api_key"`
		Model    string `json:"model"`
	}
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if appErr := service.TestAISettings(req.Endpoint, req.APIKey, req.Model); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, map[string]any{"ok": true})
}

// ImageAcceleration GET /system-settings/image-acceleration（匿名）
func (h *SettingsHandler) ImageAcceleration(c *gin.Context) {
	settings := service.AISettingsRead(h.App.Cfg, h.App.DB)
	respond.JSON(c, http.StatusOK, map[string]any{"image_acceleration_server_url": settings.ImageAccelerationURL})
}

// MiniProgramFeatures GET /system-settings/mini-program-features（匿名）
func (h *SettingsHandler) MiniProgramFeatures(c *gin.Context) {
	settings := service.AISettingsRead(h.App.Cfg, h.App.DB)
	respond.JSON(c, http.StatusOK, map[string]any{
		"inventory_mode": settings.InventoryMode,
		"huaxing_inventory_mode": settings.HuaXingInventoryMode,
		"purchase_plans_mode": settings.PurchasePlansMode,
		"purchase_records_mode": settings.PurchaseRecordsMode,
		"material_codes_mode": settings.MaterialCodesMode,
		"secondary_warehouse_mode": settings.SecondaryWarehouseMode,
	})
}

// Webhooks GET /system-settings/webhooks（超管）
func (h *SettingsHandler) Webhooks(c *gin.Context) {
	var channels []models.WebhookChannel
	if err := h.App.DB.Order("id").Find(&channels).Error; err != nil {
		respond.Error(c, service.DatabaseError(err))
		return
	}
	out := make([]map[string]any, 0, len(channels))
	for i := range channels {
		ch := &channels[i]
		var events []string
		_ = service.DecodeJSON(ch.SubscribedEvents, &events)
		url, _ := service.DecryptWebhookSecret(h.App.Cfg, ch.WebhookURLEncrypted)
		secret, _ := service.DecryptWebhookSecret(h.App.Cfg, ch.SecretEncrypted)
		out = append(out, map[string]any{
			"platform": ch.Platform, "enabled": ch.Enabled, "webhook_url": url,
			"secret": secret, "subscribed_events": events, "version": ch.Version,
		})
	}
	respond.JSON(c, http.StatusOK, out)
}

// WebhookUpdate PUT /system-settings/webhooks/{platform}（超管）
func (h *SettingsHandler) WebhookUpdate(c *gin.Context) {
	platform := strings.ToUpper(c.Param("platform"))
	var req struct {
		WebhookURL        string   `json:"webhook_url"`
		Secret            string   `json:"secret"`
		Enabled           bool     `json:"enabled"`
		SubscribedEvents  []string `json:"subscribed_events"`
		Version           int      `json:"version"`
	}
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	var channel models.WebhookChannel
	found := h.App.DB.Where("platform = ?", platform).First(&channel).Error == nil
	if found && req.Version != 0 && req.Version != channel.Version {
		respond.Error(c, service.VersionConflictErr(req.Version, channel.Version))
		return
	}
	encURL, _ := service.EncryptWebhookSecret(h.App.Cfg, req.WebhookURL)
	encSecret, _ := service.EncryptWebhookSecret(h.App.Cfg, req.Secret)
	eventsJSON := service.MustJSONString(req.SubscribedEvents)
	now := models.UTCNow()
	if !found {
		channel = models.WebhookChannel{Platform: platform, Enabled: req.Enabled,
			WebhookURLEncrypted: encURL, SecretEncrypted: encSecret,
			SubscribedEvents: models.JSON(eventsJSON), Version: 1,
			CreatedAt: now, UpdatedAt: now}
		if err := h.App.DB.Create(&channel).Error; err != nil {
			respond.Error(c, service.DatabaseError(err))
			return
		}
	} else {
		updates := map[string]any{
			"webhook_url_encrypted": encURL, "secret_encrypted": encSecret,
			"enabled": req.Enabled, "subscribed_events": models.JSON(eventsJSON),
			"version": gormExprInc(), "updated_at": now,
		}
		if err := h.App.DB.Model(&models.WebhookChannel{}).Where("platform = ?", platform).Updates(updates).Error; err != nil {
			respond.Error(c, service.DatabaseError(err))
			return
		}
		h.App.DB.Where("platform = ?", platform).First(&channel)
	}
	var events []string
	_ = service.DecodeJSON(channel.SubscribedEvents, &events)
	url, _ := service.DecryptWebhookSecret(h.App.Cfg, channel.WebhookURLEncrypted)
	secret, _ := service.DecryptWebhookSecret(h.App.Cfg, channel.SecretEncrypted)
	respond.JSON(c, http.StatusOK, map[string]any{
		"platform": channel.Platform, "enabled": channel.Enabled, "webhook_url": url,
		"secret": secret, "subscribed_events": events, "version": channel.Version,
	})
}

// WebhookTest POST /system-settings/webhooks/{platform}/test（超管）
func (h *SettingsHandler) WebhookTest(c *gin.Context) {
	platform := strings.ToUpper(c.Param("platform"))
	var req struct {
		WebhookURL string `json:"webhook_url"`
		Secret     string `json:"secret"`
	}
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	if appErr := service.TestWebhook(h.App.Cfg, platform, req.WebhookURL, req.Secret); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, map[string]any{"ok": true})
}

func gormExprInc() any { return gorm.Expr("version + 1") }

// RegisterSettings 注册设置路由。
func RegisterSettings(r *gin.RouterGroup, app *App) {
	h := NewSettingsHandler(app)
	ai := r.Group("/ai-search", auth.AuthManagement(app.Cfg, app.DB))
	ai.POST("/expand", h.AIExpand)
	ai.GET("/status", h.AIStatus)
	super := ai.Group("", auth.SuperAdmin())
	super.GET("/settings", h.AIGetSettings)
	super.PUT("/settings", h.AIUpdateSettings)
	super.POST("/settings/test", h.AITest)

	ss := r.Group("/system-settings")
	ss.GET("/image-acceleration", h.ImageAcceleration)
	ss.GET("/mini-program-features", h.MiniProgramFeatures)
	webhooks := ss.Group("/webhooks", auth.AuthManagement(app.Cfg, app.DB), auth.SuperAdmin())
	webhooks.GET("", h.Webhooks)
	webhooks.PUT("/:platform", h.WebhookUpdate)
	webhooks.POST("/:platform/test", h.WebhookTest)
}
