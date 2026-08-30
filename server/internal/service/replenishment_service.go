package service

import (
	"net/http"
	"time"

	"github.com/shopspring/decimal"
	"gorm.io/gorm"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
)

// ShanghaiTZ 上海时区（业务时间基准）。
var ShanghaiTZ = time.FixedZone("SHANGHAI", 8*3600)

// ReplenishmentDefaults 返回补库默认值。
func ReplenishmentDefaults(db *gorm.DB) (responsible string, demandDate time.Time, appErr *apperrors.AppError) {
	var latest string
	err := db.Model(&models.PurchaseMaterial{}).
		Where("TRIM(purchase_responsible) NOT IN ?", []string{"", "\\", "/", "—", "-"}).
		Order("id DESC").Limit(1).Pluck("purchase_responsible", &latest).Error
	if err != nil {
		return "", time.Time{}, DatabaseError(err)
	}
	return latest, time.Now().In(ShanghaiTZ), nil
}

// SetReplenishmentPolicy 保存安全库存策略（乐观锁）。
func SetReplenishmentPolicy(db *gorm.DB, material *models.StockMaterial, minimumQty decimal.Decimal, enabled bool, version int) *apperrors.AppError {
	if appErr := ValidateQuantityPrecision(minimumQty); appErr != nil {
		return appErr
	}
	var policy models.StockReplenishmentPolicy
	err := db.Where("stock_material_id = ?", material.ID).First(&policy).Error
	if IsNotFound(err) {
		policy = models.StockReplenishmentPolicy{
			StockMaterialID: material.ID,
			MinimumQty:      models.Decimal{Decimal: minimumQty},
			Enabled:         enabled,
			CreatedAt:       models.UTCNow(),
			UpdatedAt:       models.UTCNow(),
			Version:         1,
		}
		if err := db.Create(&policy).Error; err != nil {
			return DatabaseError(err)
		}
		return nil
	}
	if err != nil {
		return DatabaseError(err)
	}
	if appErr := ValidateVersion(version, policy.Version); appErr != nil {
		return appErr
	}
	policy.MinimumQty = models.Decimal{Decimal: minimumQty}
	policy.Enabled = enabled
	policy.Version++
	policy.UpdatedAt = models.UTCNow()
	if err := db.Model(&models.StockReplenishmentPolicy{}).Where("stock_material_id = ?", material.ID).
		Updates(map[string]any{
			"minimum_qty": minimumQty.String(),
			"enabled":     enabled,
			"version":     gorm.Expr("version + 1"),
			"updated_at":  policy.UpdatedAt,
		}).Error; err != nil {
		return DatabaseError(err)
	}
	return nil
}

// CreateReplenishmentDraft 从低库存一键生成补库申购计划草稿。
func CreateReplenishmentDraft(db *gorm.DB, stockMaterialID int64, demandDate time.Time, actualDemandPerson, purchaseResponsible string, plannedQty decimal.Decimal) (*models.PurchaseMaterial, *apperrors.AppError) {
	stock, appErr := GetStockMaterial(db, stockMaterialID)
	if appErr != nil {
		return nil, appErr
	}
	var balance models.StockBalance
	err := db.Where("stock_material_id = ?", stockMaterialID).First(&balance).Error
	if IsNotFound(err) {
		return nil, apperrors.New("BALANCE_MISSING", "库存余额记录不存在", http.StatusConflict, nil)
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	var policy models.StockReplenishmentPolicy
	policyErr := db.Where("stock_material_id = ?", stockMaterialID).First(&policy).Error
	policyMissing := IsNotFound(policyErr)
	if policyErr != nil && !policyMissing {
		return nil, DatabaseError(policyErr)
	}
	if policyMissing || !policy.Enabled || balance.Quantity.Decimal.GreaterThan(policy.MinimumQty.Decimal) {
		return nil, apperrors.New("NOT_LOW_STOCK", "该物资当前不在低库存范围", http.StatusConflict, nil)
	}
	consumption, err := RecentOutboundConsumption(db, []int64{stock.ID}, time.Now().UTC())
	if err != nil {
		return nil, DatabaseError(err)
	}
	suggested := consumption[stock.ID]
	if appErr := ValidateQuantityPrecision(plannedQty); appErr != nil {
		return nil, appErr
	}
	var previousCode string
	_ = db.Model(&models.PurchaseMaterial{}).
		Where("stock_material_id = ? AND material_code IS NOT NULL", stock.ID).
		Order("id DESC").Limit(1).Pluck("material_code", &previousCode).Error

	unit := stock.UnitName
	quantityNote := "补库计划：建议申购 " + serializeDecimal(suggested) + " " + unit
	if !plannedQty.Equal(suggested) {
		quantityNote += "，确认计划 " + serializeDecimal(plannedQty) + " " + unit
	}
	var noteParts []string
	if stock.Remark != nil && *stock.Remark != "" {
		noteParts = append(noteParts, *stock.Remark)
	}
	noteParts = append(noteParts, quantityNote)

	_, images, appErr := StockMaterialImages(db, stock.ID)
	if appErr != nil {
		return nil, appErr
	}
	imageIDs := make([]string, 0, len(images))
	for _, f := range images {
		imageIDs = append(imageIDs, f.ID)
	}
	var codePtr *string
	if previousCode != "" {
		codePtr = &previousCode
	}
	var stockIDPtr *int64
	stockID := stock.ID
	stockIDPtr = &stockID

	purchase, appErr := CreatePurchaseMaterial(db,
		demandDate,
		ptrStr(codePtr), "", "正常", "HXNI 检修维护部",
		stock.Name, stock.ModelSpec, stock.UnitName,
		actualDemandPerson, purchaseResponsible,
		plannedQty,
		"低库存补库", "", joinStrings(noteParts, "；"),
		stockIDPtr, "NORMAL", imageIDs)
	if appErr != nil {
		return nil, appErr
	}
	return purchase, nil
}

func ptrStr(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func joinStrings(parts []string, sep string) string {
	out := ""
	for i, p := range parts {
		if i > 0 {
			out += sep
		}
		out += p
	}
	return out
}
