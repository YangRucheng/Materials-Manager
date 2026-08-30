package service

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/database"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
)

// ============ 图片文件校验 ============

// ValidateImageIDs 校验 image_ids 全部存在；缺失返回 INVALID_IMAGE_ID。
func ValidateImageIDs(db *gorm.DB, imageIDs []string) ([]models.FileObject, *apperrors.AppError) {
	if len(imageIDs) == 0 {
		return nil, nil
	}
	var files []models.FileObject
	if err := db.Where("id IN ?", imageIDs).Find(&files).Error; err != nil {
		return nil, DatabaseError(err)
	}
	byID := map[string]models.FileObject{}
	for _, f := range files {
		byID[f.ID] = f
	}
	var missing []string
	for _, id := range imageIDs {
		if _, ok := byID[id]; !ok {
			missing = append(missing, id)
		}
	}
	if len(missing) > 0 {
		return nil, apperrors.New("INVALID_IMAGE_ID", "图片不存在", 0,
			map[string]any{"file_ids": missing})
	}
	ordered := make([]models.FileObject, 0, len(imageIDs))
	for _, id := range imageIDs {
		ordered = append(ordered, byID[id])
	}
	return ordered, nil
}

// ============ 二级库物资 ============

// GetStockMaterial 按 ID 查询物资。
func GetStockMaterial(db *gorm.DB, materialID int64) (*models.StockMaterial, *apperrors.AppError) {
	var item models.StockMaterial
	err := db.First(&item, materialID).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("二级库物资")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	return &item, nil
}

// GetStockMaterialByUUID 按 uuid 查询物资。
func GetStockMaterialByUUID(db *gorm.DB, materialUUID string) (*models.StockMaterial, *apperrors.AppError) {
	var item models.StockMaterial
	err := db.Where("uuid = ?", materialUUID).First(&item).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("二级库物资")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	return &item, nil
}

// StockMaterialImages 加载物资图片（file_object）。
func StockMaterialImages(db *gorm.DB, materialID int64) ([]models.StockMaterialImage, []models.FileObject, *apperrors.AppError) {
	var links []models.StockMaterialImage
	if err := db.Where("material_id = ?", materialID).Order("sort_order").Find(&links).Error; err != nil {
		return nil, nil, DatabaseError(err)
	}
	if len(links) == 0 {
		return links, nil, nil
	}
	fileIDs := make([]string, 0, len(links))
	for _, l := range links {
		fileIDs = append(fileIDs, l.FileID)
	}
	var files []models.FileObject
	if err := db.Where("id IN ?", fileIDs).Find(&files).Error; err != nil {
		return nil, nil, DatabaseError(err)
	}
	byID := map[string]models.FileObject{}
	for _, f := range files {
		byID[f.ID] = f
	}
	ordered := make([]models.FileObject, 0, len(links))
	for _, l := range links {
		if f, ok := byID[l.FileID]; ok {
			ordered = append(ordered, f)
		}
	}
	return links, ordered, nil
}

// StockMaterialHasOperations 判断物资是否已有出入库记录。
func StockMaterialHasOperations(db *gorm.DB, materialID int64) (bool, *apperrors.AppError) {
	var count int64
	if err := db.Model(&models.StockOperationLine{}).
		Where("stock_material_id = ?", materialID).Count(&count).Error; err != nil {
		return false, DatabaseError(err)
	}
	return count > 0, nil
}

// DeleteStockMaterial 删除物资（乐观锁 + 有流水则拒绝 + 解除申购计划关联）。
func DeleteStockMaterial(db *gorm.DB, item *models.StockMaterial, version int) *apperrors.AppError {
	if appErr := ValidateVersion(version, item.Version); appErr != nil {
		return appErr
	}
	hasOps, appErr := StockMaterialHasOperations(db, item.ID)
	if appErr != nil {
		return appErr
	}
	if hasOps {
		return apperrors.New("STOCK_MATERIAL_IN_USE", "该物资已有出入库操作记录，仅支持编辑，不能删除",
			http.StatusConflict, nil)
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&models.PurchaseMaterial{}).
			Where("stock_material_id = ?", item.ID).
			Update("stock_material_id", nil).Error; err != nil {
			return err
		}
		if err := tx.Delete(&models.StockMaterialImage{}, "material_id = ?", item.ID).Error; err != nil {
			return err
		}
		if err := tx.Delete(&models.StockBalance{}, "stock_material_id = ?", item.ID).Error; err != nil {
			return err
		}
		if err := tx.Delete(&models.StockReplenishmentPolicy{}, "stock_material_id = ?", item.ID).Error; err != nil {
			return err
		}
		return tx.Delete(&models.StockMaterial{}, item.ID).Error
	})
	if err != nil {
		return DatabaseError(err)
	}
	return nil
}

// CreateStockMaterial 创建二级库物资（identity_hash 唯一 + 初始化余额 0 + 图片）。
func CreateStockMaterial(db *gorm.DB, name, nameID, alias, modelSpec, unitName, remark string, imageIDs []string) (*models.StockMaterial, *apperrors.AppError) {
	files, appErr := ValidateImageIDs(db, imageIDs)
	if appErr != nil {
		return nil, appErr
	}
	item := models.StockMaterial{
		UUID:         uuid.New().String(),
		Name:         name,
		NameID:       nilOr(nameID),
		Alias:        nilOr(alias),
		ModelSpec:    modelSpec,
		UnitName:     unitName,
		Remark:       nilOr(remark),
		IdentityHash: IdentityHash(name, modelSpec, unitName),
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(&item).Error; err != nil {
			return err
		}
		balance := models.StockBalance{StockMaterialID: item.ID, Quantity: models.NewDecimal("0")}
		if err := tx.Create(&balance).Error; err != nil {
			return err
		}
		return replaceStockMaterialImages(tx, item.ID, files)
	})
	if err != nil {
		if database.IsDuplicateError(err) {
			return nil, apperrors.New("DUPLICATE_MATERIAL", "相同名称、型号规格和单位的物资已存在",
				http.StatusConflict, nil)
		}
		return nil, DatabaseError(err)
	}
	return &item, nil
}

// UpdateStockMaterial 更新物资（乐观锁 + identity_hash 重算 + 图片替换）。
func UpdateStockMaterial(db *gorm.DB, item *models.StockMaterial, name, nameID, alias, modelSpec, unitName, remark string, imageIDs []string, version int) (*models.StockMaterial, *apperrors.AppError) {
	if appErr := ValidateVersion(version, item.Version); appErr != nil {
		return nil, appErr
	}
	files, appErr := ValidateImageIDs(db, imageIDs)
	if appErr != nil {
		return nil, appErr
	}
	item.Name = name
	item.NameID = nilOr(nameID)
	item.Alias = nilOr(alias)
	item.ModelSpec = modelSpec
	item.UnitName = unitName
	item.Remark = nilOr(remark)
	item.IdentityHash = IdentityHash(name, modelSpec, unitName)
	item.Version++
	item.UpdatedAt = models.UTCNow()
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&item).Select("Name", "NameID", "Alias", "ModelSpec", "UnitName", "Remark", "IdentityHash", "Version", "UpdatedAt").Updates(item).Error; err != nil {
			return err
		}
		return replaceStockMaterialImages(tx, item.ID, files)
	})
	if err != nil {
		if database.IsDuplicateError(err) {
			return nil, apperrors.New("DUPLICATE_MATERIAL", "相同名称、型号规格和单位的物资已存在",
				http.StatusConflict, nil)
		}
		return nil, DatabaseError(err)
	}
	return item, nil
}

func replaceStockMaterialImages(tx *gorm.DB, materialID int64, files []models.FileObject) error {
	if err := tx.Delete(&models.StockMaterialImage{}, "material_id = ?", materialID).Error; err != nil {
		return err
	}
	if len(files) == 0 {
		return nil
	}
	links := make([]models.StockMaterialImage, 0, len(files))
	for i, f := range files {
		links = append(links, models.StockMaterialImage{MaterialID: materialID, FileID: f.ID, SortOrder: i})
	}
	return tx.Create(&links).Error
}

// SearchStockMaterials 分页 + OR 搜索（name/name_id/alias/model_spec）。
func SearchStockMaterials(db *gorm.DB, keyword string, page, pageSize int) ([]models.StockMaterial, int, *apperrors.AppError) {
	q := db.Model(&models.StockMaterial{})
	if clause, args := ContainsAnyClause(
		[]string{"name", "name_id", "alias", "model_spec"}, keyword); clause != "" {
		q = q.Where(clause, args...)
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	var items []models.StockMaterial
	if err := q.Order("id DESC").Offset((page - 1) * pageSize).Limit(pageSize).Find(&items).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	return items, int(total), nil
}

func nilOr(value string) *string {
	if value == "" {
		return nil
	}
	v := value
	return &v
}

// StockMaterialWithBalance 物资详情（余额 + 策略 + 图片 + 流水标记）。
type StockMaterialWithBalance struct {
	Material      *models.StockMaterial
	BalanceQty    decimal.Decimal
	Policy        *models.StockReplenishmentPolicy
	Images        []models.FileObject
	HasOperations bool
}

// LoadStockMaterialDetail 加载物资完整详情。
func LoadStockMaterialDetail(db *gorm.DB, materialID int64) (*StockMaterialWithBalance, *apperrors.AppError) {
	material, appErr := GetStockMaterial(db, materialID)
	if appErr != nil {
		return nil, appErr
	}
	detail := &StockMaterialWithBalance{Material: material, BalanceQty: decimal.Zero}
	var balance models.StockBalance
	if err := db.Where("stock_material_id = ?", materialID).First(&balance).Error; err == nil {
		detail.BalanceQty = balance.Quantity.Decimal
	}
	var policy models.StockReplenishmentPolicy
	if err := db.Where("stock_material_id = ?", materialID).First(&policy).Error; err == nil {
		detail.Policy = &policy
	}
	_, images, appErr := StockMaterialImages(db, materialID)
	if appErr != nil {
		return nil, appErr
	}
	detail.Images = images
	hasOps, appErr := StockMaterialHasOperations(db, materialID)
	if appErr != nil {
		return nil, appErr
	}
	detail.HasOperations = hasOps
	return detail, nil
}

// ============ 申购计划（补库草稿依赖，P4 完整实现） ============

// NextPurchasePlanNo 生成 PLAN-YYYYMMDD-NNN 计划号（并查 material 与快照取最大值）。
func NextPurchasePlanNo(db *gorm.DB, planDate time.Time) (string, *apperrors.AppError) {
	prefix := "PLAN-" + planDate.Format("20060102") + "-"
	var materialMax, snapshotMax string
	_ = db.Model(&models.PurchaseMaterial{}).Where("plan_no LIKE ?", prefix+"%").
		Order("plan_no DESC").Limit(1).Pluck("plan_no", &materialMax).Error
	_ = db.Model(&models.PurchaseRequestLine{}).Where("plan_no_snapshot LIKE ?", prefix+"%").
		Order("plan_no_snapshot DESC").Limit(1).Pluck("plan_no_snapshot", &snapshotMax).Error
	previous := materialMax
	if strings.Compare(snapshotMax, previous) > 0 {
		previous = snapshotMax
	}
	index := 1
	if previous != "" {
		parts := strings.Split(previous, "-")
		if n, err := strconv.Atoi(parts[len(parts)-1]); err == nil {
			index = n + 1
		}
	}
	if index > 999 {
		return "", apperrors.New("PLAN_DAILY_LIMIT_EXCEEDED", "同一计划日期最多创建 999 条申购计划",
			http.StatusConflict, nil)
	}
	return prefix + strconv.Itoa(index), nil
}

// CreatePurchaseMaterial 创建申购计划（供补库草稿使用；P4 扩展完整字段）。
func CreatePurchaseMaterial(db *gorm.DB, planDate time.Time, materialCode, category, urgency, demandDepartment, name, modelSpec, unitName, actualDemandPerson, purchaseResponsible string, plannedQty decimal.Decimal, usage, subitemNo, remark string, stockMaterialID *int64, status string, imageIDs []string) (*models.PurchaseMaterial, *apperrors.AppError) {
	responsible := purchaseResponsible
	if responsible == "" {
		responsible = "\\"
	}
	person := actualDemandPerson
	if person == "" {
		person = responsible
	}
	if appErr := ValidateQuantityPrecision(plannedQty); appErr != nil {
		return nil, appErr
	}
	files, appErr := ValidateImageIDs(db, imageIDs)
	if appErr != nil {
		return nil, appErr
	}
	if stockMaterialID != nil {
		if _, err := GetStockMaterial(db, *stockMaterialID); err != nil {
			return nil, err
		}
	}
	planNo, appErr := NextPurchasePlanNo(db, planDate)
	if appErr != nil {
		return nil, appErr
	}
	item := models.PurchaseMaterial{
		PlanNo:              planNo,
		PlanDate:            planDate,
		MaterialCode:        nilOr(materialCode),
		Category:            nilOr(category),
		Urgency:             urgency,
		DemandDepartment:    demandDepartment,
		Name:                name,
		ModelSpec:           modelSpec,
		UnitName:            unitName,
		ActualDemandPerson:  person,
		PurchaseResponsible: responsible,
		PlannedQty:          models.Decimal{Decimal: plannedQty},
		Usage:               usage,
		SubitemNo:           nilOr(subitemNo),
		Remark:              nilOr(remark),
		StockMaterialID:     stockMaterialID,
		Status:              status,
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(&item).Error; err != nil {
			return err
		}
		if len(files) == 0 {
			return nil
		}
		links := make([]models.PurchaseMaterialImage, 0, len(files))
		for i, f := range files {
			links = append(links, models.PurchaseMaterialImage{MaterialID: item.ID, FileID: f.ID, SortOrder: i})
		}
		return tx.Create(&links).Error
	})
	if err != nil {
		if database.IsDuplicateError(err) {
			return nil, apperrors.New("PLAN_NO_CONFLICT", "计划号生成冲突，请稍后重试",
				http.StatusConflict, nil)
		}
		return nil, DatabaseError(err)
	}
	return &item, nil
}
