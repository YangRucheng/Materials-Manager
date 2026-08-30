// Package service 小程序业务逻辑。
package service

import (
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/shopspring/decimal"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/domain"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
	"github.com/yangrucheng/materials-manager/server/internal/wechat"
)

// WXClient 全局微信客户端。
var WXClient = wechat.New()

// WeChatCredentials 解析配置的 appID/appSecret 对。
func WeChatCredentials(cfg *config.Config, appID string) (string, string, *apperrors.AppError) {
	appIDs := splitNonEmpty(cfg.WechatMiniProgramAppID)
	appSecrets := splitNonEmpty(cfg.WechatMiniProgramAppSecret)
	if len(appIDs) == 0 || len(appIDs) != len(appSecrets) || len(appIDs) != len(uniqueStrings(appIDs)) {
		return "", "", apperrors.New("WECHAT_CONFIGURATION_INVALID",
			"微信小程序 AppID 与 AppSecret 配置无效", http.StatusServiceUnavailable,
			map[string]any{"app_id_count": len(appIDs), "app_secret_count": len(appSecrets)})
	}
	effective := appID
	if effective == "" {
		effective = appIDs[0]
	}
	for i, id := range appIDs {
		if id == effective {
			return id, appSecrets[i], nil
		}
	}
	return "", "", apperrors.New("WECHAT_NOT_CONFIGURED", "当前微信小程序登录尚未配置",
		http.StatusServiceUnavailable, map[string]any{"app_id": effective})
}

func splitNonEmpty(s string) []string {
	var out []string
	for _, part := range strings.Split(s, ",") {
		if trimmed := strings.TrimSpace(part); trimmed != "" {
			out = append(out, trimmed)
		}
	}
	return out
}

func uniqueStrings(list []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, s := range list {
		if !seen[s] {
			seen[s] = true
			out = append(out, s)
		}
	}
	return out
}

// WXLogin 微信登录：已注册返 access_token，未注册返 registration_token + requires_profile。
func WXLogin(cfg *config.Config, db *gorm.DB, code, appID string) (accessToken, refreshToken string, user *models.MiniProgramUser, requiresProfile bool, registrationToken string, appErr *apperrors.AppError) {
	effectiveAppID, appSecret, appErr := WeChatCredentials(cfg, appID)
	if appErr != nil {
		return "", "", nil, false, "", appErr
	}
	openid, _, err := WXClient.Code2Session(effectiveAppID, appSecret, code)
	if err != nil {
		return "", "", nil, false, "", apperrors.New("WECHAT_AUTH_FAILED", "微信登录失败，请稍后重试", http.StatusUnauthorized, nil)
	}
	// 查找身份
	var identity models.MiniProgramIdentity
	if err := db.Where("app_id = ? AND wechat_openid = ?", effectiveAppID, openid).First(&identity).Error; err == nil {
		var mpUser models.MiniProgramUser
		if err := db.First(&mpUser, identity.MiniProgramUserID).Error; err == nil {
			if !mpUser.Enabled {
				return "", "", nil, false, "", apperrors.New("ACCOUNT_DISABLED", "您的账号待审核，请联系管理员", http.StatusForbidden, nil)
			}
			access, _ := security.NewMiniProgramAccessToken(cfg.JWTSecret, cfg.JWTAlgorithm, mpUser.ID, cfg.TokenExpireAccess())
			return access, "", &mpUser, false, "", nil
		}
	}
	// 新用户：登记开关
	settings := GetSettingData(db)
	if !SettingBool(settings, "mini_program_registration_enabled", true) {
		return "", "", nil, false, "", apperrors.New("ACCOUNT_DISABLED", "暂不支持新用户注册，请联系管理员", http.StatusForbidden, nil)
	}
	regToken, _ := security.NewMiniProgramRegistrationToken(cfg.JWTSecret, cfg.JWTAlgorithm, effectiveAppID, openid, 10*time.Minute)
	return "", "", nil, true, regToken, nil
}

// RegisterProfile 完善资料注册（registration token）。
func RegisterProfile(cfg *config.Config, db *gorm.DB, appID, openid, displayName, departmentName string) (accessToken string, user *models.MiniProgramUser, appErr *apperrors.AppError) {
	// 幂等：已存在直接返回
	var existing models.MiniProgramIdentity
	if err := db.Where("app_id = ? AND wechat_openid = ?", appID, openid).First(&existing).Error; err == nil {
		var mpUser models.MiniProgramUser
		if err := db.First(&mpUser, existing.MiniProgramUserID).Error; err == nil {
			access, _ := security.NewMiniProgramAccessToken(cfg.JWTSecret, cfg.JWTAlgorithm, mpUser.ID, cfg.TokenExpireAccess())
			return access, &mpUser, nil
		}
	}
	settings := GetSettingData(db)
	enabled := SettingBool(settings, "mini_program_new_user_enabled", true)
	if !SettingBool(settings, "mini_program_registration_enabled", true) {
		return "", nil, apperrors.New("ACCOUNT_DISABLED", "暂不支持新用户注册，请联系管理员", http.StatusForbidden, nil)
	}
	mpUser := models.MiniProgramUser{
		DisplayName:    displayName,
		DepartmentName: departmentName,
		Enabled:        enabled,
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(&mpUser).Error; err != nil {
			return err
		}
		identity := models.MiniProgramIdentity{
			MiniProgramUserID: mpUser.ID, AppID: appID, WechatOpenid: openid,
		}
		return tx.Create(&identity).Error
	})
	if err != nil {
		return "", nil, apperrors.New("DATA_CONFLICT", "微信身份已绑定其他账号", http.StatusConflict, nil)
	}
	if !enabled {
		return "", &mpUser, nil
	}
	access, _ := security.NewMiniProgramAccessToken(cfg.JWTSecret, cfg.JWTAlgorithm, mpUser.ID, cfg.TokenExpireAccess())
	return access, &mpUser, nil
}

// MiniInventoryItem 小程序库存条目。
type MiniInventoryItem struct {
	MaterialID  int64
	UUID        string
	Name        string
	NameID      *string
	Alias       *string
	ModelSpec   string
	UnitName    string
	Quantity    decimal.Decimal
	MinimumQty  *decimal.Decimal
	StockStatus string
	Remark      *string
}

// SearchMiniInventory 小程序库存查询。
func SearchMiniInventory(db *gorm.DB, keyword string, stockStatus string, page, pageSize int) ([]MiniInventoryItem, int, *apperrors.AppError) {
	q := db.Table("stock_material").
		Joins("LEFT JOIN stock_balance ON stock_balance.stock_material_id = stock_material.id").
		Joins("LEFT JOIN stock_replenishment_policy ON stock_replenishment_policy.stock_material_id = stock_material.id").
		Select("stock_material.id AS material_id, stock_material.uuid, stock_material.name, stock_material.name_id, stock_material.alias, stock_material.model_spec, stock_material.unit_name, stock_material.remark, COALESCE(stock_balance.quantity, 0) AS quantity, stock_replenishment_policy.minimum_qty, stock_replenishment_policy.enabled AS policy_enabled")
	if clause, args := ContainsAnyClause(
		[]string{"stock_material.name", "stock_material.name_id", "stock_material.alias", "stock_material.model_spec"}, keyword); clause != "" {
		q = q.Where(clause, args...)
	}
	q = q.Where("stock_material.`uuid` != ''")
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	type row struct {
		MaterialID    int64
		UUID          string
		Name          string
		NameID        *string
		Alias         *string
		ModelSpec     string
		UnitName      string
		Remark        *string
		Quantity      models.Decimal
		MinimumQty    *models.Decimal
		PolicyEnabled bool
	}
	var rows []row
	if err := q.Order("stock_material.id DESC").Offset((page - 1) * pageSize).Limit(pageSize).Scan(&rows).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	items := make([]MiniInventoryItem, 0, len(rows))
	for _, r := range rows {
		status := domain.MiniStockNormal
		if r.Quantity.Decimal.LessThanOrEqual(decimal.Zero) {
			status = domain.MiniStockOutOfStock
		} else if r.PolicyEnabled && r.Quantity.Decimal.LessThanOrEqual(r.MinimumQty.Decimal) {
			status = domain.MiniStockLowStock
		}
		var minPtr *decimal.Decimal
		if r.PolicyEnabled {
			min := r.MinimumQty.Decimal
			minPtr = &min
		}
		items = append(items, MiniInventoryItem{
			MaterialID: r.MaterialID, UUID: r.UUID, Name: r.Name, NameID: r.NameID,
			Alias: r.Alias, ModelSpec: r.ModelSpec, UnitName: r.UnitName,
			Quantity: r.Quantity.Decimal, MinimumQty: minPtr, StockStatus: status, Remark: r.Remark,
		})
	}
	return items, int(total), nil
}

// MiniPurchasePlanItem 小程序申购计划条目。
type MiniPurchasePlanItem struct {
	ID                 int64
	Name               string
	ModelSpec          string
	UnitName           string
	PlannedQty         decimal.Decimal
	ActualDemandPerson string
	SubitemNo          *string
	PlanNo             string
}

// SearchMiniPurchasePlans 未转入记录的申购计划。
func SearchMiniPurchasePlans(db *gorm.DB, keyword string, page, pageSize int) ([]MiniPurchasePlanItem, int, *apperrors.AppError) {
	q := db.Model(&models.PurchaseMaterial{}).
		Where("status = ?", domain.PlanNormal).
		Where("NOT EXISTS (SELECT 1 FROM purchase_request_line WHERE purchase_request_line.purchase_material_id = purchase_material.id)")
	if clause, args := ContainsAnyClause([]string{"name", "model_spec"}, keyword); clause != "" {
		q = q.Where(clause, args...)
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	var materials []models.PurchaseMaterial
	if err := q.Order("id DESC").Offset((page - 1) * pageSize).Limit(pageSize).Find(&materials).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	items := make([]MiniPurchasePlanItem, 0, len(materials))
	for _, m := range materials {
		items = append(items, MiniPurchasePlanItem{
			ID: m.ID, Name: m.Name, ModelSpec: m.ModelSpec, UnitName: m.UnitName,
			PlannedQty: m.PlannedQty.Decimal, ActualDemandPerson: m.ActualDemandPerson,
			SubitemNo: m.SubitemNo, PlanNo: m.PlanNo,
		})
	}
	return items, int(total), nil
}

// MiniPurchaseRecordItem 小程序申购记录条目。
type MiniPurchaseRecordItem struct {
	ID           int64
	MaterialName string
	ModelSpec    string
	UnitName     string
	PurchaseQty  decimal.Decimal
	Status       string
	PlanNo       string
}

// SearchMiniPurchaseRecords 小程序申购记录。
func SearchMiniPurchaseRecords(db *gorm.DB, keyword string, page, pageSize int) ([]MiniPurchaseRecordItem, int, *apperrors.AppError) {
	q := db.Model(&models.PurchaseRequestLine{})
	if clause, args := ContainsAnyClause(
		[]string{"material_name_snapshot", "model_spec_snapshot", "trace_no", "plan_no_snapshot"}, keyword); clause != "" {
		q = q.Where(clause, args...)
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	var lines []models.PurchaseRequestLine
	if err := q.Order("id DESC").Offset((page - 1) * pageSize).Limit(pageSize).Find(&lines).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	items := make([]MiniPurchaseRecordItem, 0, len(lines))
	for _, l := range lines {
		items = append(items, MiniPurchaseRecordItem{
			ID: l.ID, MaterialName: l.MaterialNameSnapshot, ModelSpec: l.ModelSpecSnapshot,
			UnitName: l.UnitNameSnapshot, PurchaseQty: l.PurchaseQty.Decimal,
			Status: l.Status, PlanNo: l.PlanNoSnapshot,
		})
	}
	return items, int(total), nil
}

// MiniOutbound 小程序出库。
func MiniOutbound(db *gorm.DB, materialUUID, clientRequestID string, occurredAt time.Time, quantity decimal.Decimal, businessReason string, receiverUnit, subitemNo *string, miniUser *models.MiniProgramUser) (*models.StockOperation, *apperrors.AppError) {
	if appErr := ValidateQuantityPrecision(quantity); appErr != nil {
		return nil, appErr
	}
	if quantity.LessThanOrEqual(decimal.Zero) {
		return nil, apperrors.New("VALIDATION_ERROR", "出库数量必须大于 0", 422, nil)
	}
	material, appErr := GetStockMaterialByUUID(db, materialUUID)
	if appErr != nil {
		return nil, appErr
	}
	if businessReason == "" {
		return nil, apperrors.New("BUSINESS_REASON_REQUIRED", "出库必须填写用途", 0, nil)
	}
	name := miniUser.DisplayName
	input := &OperationInput{
		ClientRequestID: clientRequestID,
		OccurredAt:      occurredAt.UTC(),
		SourceType:      domain.SourceMiniProgram,
		BusinessReason:  businessReason,
		ReceiverUnit:    receiverUnit,
		ReceiverName:    &name,
		SubitemNo:       subitemNo,
		Lines:           []OperationLineInput{{StockMaterialID: material.ID, Quantity: quantity}},
	}
	return CreateOperation(db, input, domain.OperationOutbound, nil, nil, &name)
}

// MiniProgramUsers 管理端小程序用户列表。
func MiniProgramUsers(db *gorm.DB, keyword string, page, pageSize int) ([]models.MiniProgramUser, int, *apperrors.AppError) {
	q := db.Model(&models.MiniProgramUser{})
	if keyword != "" {
		like := "%" + keyword + "%"
		q = q.Where("display_name LIKE ? OR department_name LIKE ?", like, like)
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	var items []models.MiniProgramUser
	if err := q.Order("id").Offset((page - 1) * pageSize).Limit(pageSize).Find(&items).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	// 载入身份
	for i := range items {
		db.Where("mini_program_user_id = ?", items[i].ID).Order("app_id").Find(&items[i].Identities)
	}
	return items, int(total), nil
}

// MergeMiniUsers 合并小程序账号（迁移身份 + 删源账号）。
func MergeMiniUsers(db *gorm.DB, targetID, sourceID int64, targetVersion, sourceVersion int) (*models.MiniProgramUser, *apperrors.AppError) {
	var target, source models.MiniProgramUser
	if err := db.First(&target, targetID).Error; err != nil {
		return nil, apperrors.NotFound("小程序用户")
	}
	if err := db.First(&source, sourceID).Error; err != nil {
		return nil, apperrors.NotFound("小程序用户")
	}
	if appErr := ValidateVersion(targetVersion, target.Version); appErr != nil {
		return nil, appErr
	}
	if appErr := ValidateVersion(sourceVersion, source.Version); appErr != nil {
		return nil, appErr
	}
	if target.DisplayName != source.DisplayName || target.DepartmentName != source.DepartmentName {
		return nil, apperrors.New("MERGE_IDENTITY_MISMATCH", "两个账号的姓名或部门不一致，无法合并", http.StatusConflict, nil)
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		var sourceIdentities []models.MiniProgramIdentity
		if err := tx.Where("mini_program_user_id = ?", sourceID).Find(&sourceIdentities).Error; err != nil {
			return err
		}
		var targetIdentities []models.MiniProgramIdentity
		if err := tx.Where("mini_program_user_id = ?", targetID).Find(&targetIdentities).Error; err != nil {
			return err
		}
		targetAppIDs := map[string]bool{}
		for _, id := range targetIdentities {
			targetAppIDs[id.AppID] = true
		}
		for _, id := range sourceIdentities {
			if targetAppIDs[id.AppID] {
				return apperrors.New("MERGE_APP_ID_CONFLICT", "两个账号绑定了同一小程序的微信身份，无法合并", http.StatusConflict, nil)
			}
		}
		if err := tx.Model(&models.MiniProgramIdentity{}).
			Where("mini_program_user_id = ?", sourceID).
			Update("mini_program_user_id", targetID).Error; err != nil {
			return err
		}
		return tx.Delete(&models.MiniProgramUser{}, sourceID).Error
	})
	if err != nil {
		var appErr *apperrors.AppError
		if errors.As(err, &appErr) {
			return nil, appErr
		}
		return nil, DatabaseError(err)
	}
	var updated models.MiniProgramUser
	db.First(&updated, targetID)
	return &updated, nil
}

// MiniOutboundReasons 出库原因下拉。
func MiniOutboundReasons() []string {
	return []string{"现场维护", "设备检修", "技术改造", "日常消耗", "其他"}
}

// MiniOperationByNo 按流水号查询小程序出库详情。
func MiniOperationByNo(db *gorm.DB, operationNo string) (*models.StockOperation, *apperrors.AppError) {
	var item models.StockOperation
	err := db.Where("operation_no = ?", operationNo).First(&item).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("出库记录")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	db.Where("operation_id = ?", item.ID).Order("id").Find(&item.Lines)
	return &item, nil
}
