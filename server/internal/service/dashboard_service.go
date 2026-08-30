package service

import (
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/domain"
	"github.com/yangrucheng/materials-manager/server/internal/models"
)

// DashboardSummary 工作台聚合计数。
func DashboardSummary(db *gorm.DB) (stockCount, lowCount, uncodedCount, recordCount int) {
	if IsLiteSecondaryWarehouse(db) {
		stockCount = countRows(db, &models.LiteInventory{})
		lowCount = 0
	} else {
		stockCount = countRows(db, &models.StockMaterial{})
		lowCount = countLowStock(db)
	}
	uncodedCount = countUncoded(db)
	recordCount = countRows(db, &models.PurchaseRequestLine{})
	return stockCount, lowCount, uncodedCount, recordCount
}

func countRows(db *gorm.DB, model any) int {
	var count int64
	if err := db.Model(model).Count(&count).Error; err != nil {
		return 0
	}
	return int(count)
}

func countLowStock(db *gorm.DB) int {
	var count int64
	err := db.Model(&models.StockMaterial{}).
		Joins("JOIN stock_balance ON stock_balance.stock_material_id = stock_material.id").
		Joins("JOIN stock_replenishment_policy ON stock_replenishment_policy.stock_material_id = stock_material.id").
		Where("stock_replenishment_policy.enabled = ?", true).
		Where("stock_balance.quantity <= stock_replenishment_policy.minimum_qty").
		Count(&count).Error
	if err != nil {
		return 0
	}
	return int(count)
}

func countUncoded(db *gorm.DB) int {
	var count int64
	err := db.Model(&models.PurchaseMaterial{}).
		Where("material_code IS NULL AND status = ?", domain.PlanNormal).
		Count(&count).Error
	if err != nil {
		return 0
	}
	return int(count)
}
