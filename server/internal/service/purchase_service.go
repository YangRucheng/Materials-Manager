// Package service 申购域业务逻辑（计划/记录/模板/分享/同步）。
package service

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/shopspring/decimal"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"

	"github.com/yangrucheng/materials-manager/server/internal/database"
	"github.com/yangrucheng/materials-manager/server/internal/domain"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
)

// ============ 申购计划 read 组装 ============

// PurchaseMaterialReadData 承载计划 read 的关联数据。
type PurchaseMaterialReadData struct {
	StockMaterialName *string
	Images            []models.FileObject
	MovedToRecord     bool
}

// LoadPurchaseMaterialReadData 加载计划关联（物资名/图片/是否已转入）。
func LoadPurchaseMaterialReadData(db *gorm.DB, item *models.PurchaseMaterial, movedIDs map[int64]bool) (*PurchaseMaterialReadData, *apperrors.AppError) {
	data := &PurchaseMaterialReadData{}
	if item.StockMaterialID != nil {
		var stock models.StockMaterial
		if err := db.Select("name").First(&stock, *item.StockMaterialID).Error; err == nil {
			data.StockMaterialName = &stock.Name
		}
	}
	var links []models.PurchaseMaterialImage
	if err := db.Where("material_id = ?", item.ID).Order("sort_order").Find(&links).Error; err != nil {
		return nil, DatabaseError(err)
	}
	if len(links) > 0 {
		fileIDs := make([]string, 0, len(links))
		for _, l := range links {
			fileIDs = append(fileIDs, l.FileID)
		}
		var files []models.FileObject
		if err := db.Where("id IN ?", fileIDs).Find(&files).Error; err != nil {
			return nil, DatabaseError(err)
		}
		byID := map[string]models.FileObject{}
		for _, f := range files {
			byID[f.ID] = f
		}
		for _, l := range links {
			if f, ok := byID[l.FileID]; ok {
				data.Images = append(data.Images, f)
			}
		}
	}
	if movedIDs == nil {
		var count int64
		db.Model(&models.PurchaseRequestLine{}).
			Where("purchase_material_id = ?", item.ID).Count(&count)
		data.MovedToRecord = count > 0
	} else {
		data.MovedToRecord = movedIDs[item.ID]
	}
	return data, nil
}

// GetPurchaseMaterial 查询申购计划。
func GetPurchaseMaterial(db *gorm.DB, materialID int64) (*models.PurchaseMaterial, *apperrors.AppError) {
	var item models.PurchaseMaterial
	err := db.First(&item, materialID).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("申购计划")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	return &item, nil
}

// PurchaseMaterialIDsMovedToRecord 批量判断哪些计划已转入记录。
func PurchaseMaterialIDsMovedToRecord(db *gorm.DB, ids []int64) (map[int64]bool, *apperrors.AppError) {
	out := map[int64]bool{}
	if len(ids) == 0 {
		return out, nil
	}
	var moved []int64
	if err := db.Model(&models.PurchaseRequestLine{}).
		Where("purchase_material_id IN ?", ids).Distinct().Pluck("purchase_material_id", &moved).Error; err != nil {
		return nil, DatabaseError(err)
	}
	for _, id := range moved {
		out[id] = true
	}
	return out, nil
}

// SearchPurchaseMaterials 计划列表（完整筛选）。
func SearchPurchaseMaterials(db *gorm.DB, keyword, searchField, searchValue, name, modelSpec, actualDemandPerson string, emptyActualDemandPerson bool, purchaseResponsible, subitemNo string, emptySubitemNo bool, category string, status []string, coded *bool, moved *bool, page, pageSize int, sortBy, sortOrder string) ([]models.PurchaseMaterial, int, *apperrors.AppError) {
	q := db.Model(&models.PurchaseMaterial{})
	if clause, args := ContainsAnyClause([]string{
		"plan_no", "CAST(plan_date AS CHAR)", "name", "model_spec", "material_code",
		"category", "unit_name", "CAST(planned_qty AS CHAR)", "actual_demand_person",
		"purchase_responsible", "usage", "subitem_no", "remark",
	}, keyword); clause != "" {
		q = q.Where(clause, args...)
	}
	searchColumns := map[string]string{
		"plan_no": "plan_no", "plan_date": "CAST(plan_date AS CHAR)", "material_code": "material_code",
		"category": "category", "name": "name", "model_spec": "model_spec", "unit_name": "unit_name",
		"planned_qty": "CAST(planned_qty AS CHAR)", "usage": "usage", "subitem_no": "subitem_no", "remark": "remark",
	}
	if col, ok := searchColumns[searchField]; ok && searchValue != "" {
		if clause, args := ContainsAnyClause([]string{col}, searchValue); clause != "" {
			q = q.Where(clause, args...)
		}
	}
	if clause, args := ContainsAnyClause([]string{"name"}, name); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"model_spec"}, modelSpec); clause != "" {
		q = q.Where(clause, args...)
	}
	if emptyActualDemandPerson {
		q = q.Where("(actual_demand_person IS NULL OR TRIM(actual_demand_person) IN ?)",
			[]string{"", "\\", "/", "—", "-"})
	} else if clause, args := ContainsAnyClause([]string{"actual_demand_person"}, actualDemandPerson); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"purchase_responsible"}, purchaseResponsible); clause != "" {
		q = q.Where(clause, args...)
	}
	if emptySubitemNo {
		q = q.Where("(subitem_no IS NULL OR TRIM(subitem_no) = '')")
	} else if subitemNo != "" {
		q = q.Where("TRIM(subitem_no) = ?", strings.TrimSpace(subitemNo))
	}
	if category != "" {
		q = q.Where("TRIM(category) = ?", strings.TrimSpace(category))
	}
	if len(status) > 0 {
		q = q.Where("status IN ?", status)
	}
	if coded != nil {
		if *coded {
			q = q.Where("material_code IS NOT NULL")
		} else {
			q = q.Where("material_code IS NULL")
		}
	}
	if moved != nil {
		sub := db.Model(&models.PurchaseRequestLine{}).
			Select("1").Where("purchase_material_id = purchase_material.id")
		if *moved {
			q = q.Where("EXISTS (?)", sub)
		} else {
			q = q.Where("NOT EXISTS (?)", sub)
		}
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	orderCol := ""
	switch sortBy {
	case "plan_no", "plan_date", "material_code", "category", "urgency", "demand_department",
		"name", "model_spec", "unit_name", "planned_qty", "actual_demand_person",
		"purchase_responsible", "subitem_no", "usage":
		orderCol = sortBy
	}
	if orderCol != "" {
		dir := "DESC"
		if sortOrder == "asc" {
			dir = "ASC"
		}
		q = q.Order(orderCol + " " + dir).Order("id DESC")
	} else {
		q = q.Order("id DESC")
	}
	var items []models.PurchaseMaterial
	if err := q.Offset((page - 1) * pageSize).Limit(pageSize).Find(&items).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	return items, int(total), nil
}

// PurchaseFilterOptions 计划筛选下拉。
func PurchaseFilterOptions(db *gorm.DB, moved *bool, status []string) ([]string, []string, []string, []string, *apperrors.AppError) {
	build := func() *gorm.DB {
		q := db.Model(&models.PurchaseMaterial{})
		if moved != nil {
			sub := db.Model(&models.PurchaseRequestLine{}).
				Select("1").Where("purchase_material_id = purchase_material.id")
			if *moved {
				q = q.Where("EXISTS (?)", sub)
			} else {
				q = q.Where("NOT EXISTS (?)", sub)
			}
		}
		if len(status) > 0 {
			q = q.Where("status IN ?", status)
		}
		return q
	}
	var persons, responsibles, subitems, categories []*string
	if err := build().Distinct().Order("actual_demand_person").Pluck("actual_demand_person", &persons).Error; err != nil {
		return nil, nil, nil, nil, DatabaseError(err)
	}
	if err := build().Distinct().Order("purchase_responsible").Pluck("purchase_responsible", &responsibles).Error; err != nil {
		return nil, nil, nil, nil, DatabaseError(err)
	}
	if err := build().Distinct().Order("subitem_no").Pluck("subitem_no", &subitems).Error; err != nil {
		return nil, nil, nil, nil, DatabaseError(err)
	}
	if err := build().Distinct().Order("category").Pluck("category", &categories).Error; err != nil {
		return nil, nil, nil, nil, DatabaseError(err)
	}
	return derefNonEmpty(persons), derefNonEmpty(responsibles), derefNonEmpty(subitems), derefNonEmpty(categories), nil
}

// derefNonEmpty 把可空字符串指针列表转为非空字符串列表。
func derefNonEmpty(list []*string) []string {
	out := make([]string, 0, len(list))
	for _, p := range list {
		if p != nil && *p != "" {
			out = append(out, *p)
		}
	}
	return out
}

// CreatePurchaseMaterialFull 完整创建申购计划（含计划号重试）。
func CreatePurchaseMaterialFull(db *gorm.DB, planDate *time.Time, materialCode, category, urgency, demandDepartment, name, modelSpec, unitName string, actualDemandPerson, purchaseResponsible *string, plannedQty decimal.Decimal, usage, subitemNo, remark string, stockMaterialID *int64, status, planNo string, imageIDs []string) (*models.PurchaseMaterial, *apperrors.AppError) {
	responsible := ""
	if purchaseResponsible != nil {
		responsible = *purchaseResponsible
	}
	if responsible == "" {
		responsible = "\\"
	}
	person := ""
	if actualDemandPerson != nil {
		person = *actualDemandPerson
	}
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
	if planDate == nil {
		d := time.Now().In(ShanghaiTZ)
		planDate = &d
	}
	if status == "" {
		status = domain.PlanNormal
	}
	item := &models.PurchaseMaterial{
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
	var result *models.PurchaseMaterial
	for attempt := 0; attempt < 3; attempt++ {
		planNoValue := planNo
		if planNoValue == "" {
			p, appErr := NextPurchasePlanNo(db, *planDate)
			if appErr != nil {
				return nil, appErr
			}
			planNoValue = p
		}
		item.PlanNo = planNoValue
		item.PlanDate = *planDate
		err := db.Transaction(func(tx *gorm.DB) error {
			if err := tx.Create(item).Error; err != nil {
				return err
			}
			return replacePurchaseMaterialImages(tx, item.ID, files)
		})
		if err == nil {
			result = item
			break
		}
		if database.IsDuplicateError(err) && planNo == "" {
			continue
		}
		return nil, DatabaseError(err)
	}
	if result == nil {
		return nil, apperrors.New("PLAN_NO_CONFLICT", "计划号生成冲突，请稍后重试", http.StatusConflict, nil)
	}
	return result, nil
}

func replacePurchaseMaterialImages(tx *gorm.DB, materialID int64, files []models.FileObject) error {
	if err := tx.Delete(&models.PurchaseMaterialImage{}, "material_id = ?", materialID).Error; err != nil {
		return err
	}
	if len(files) == 0 {
		return nil
	}
	links := make([]models.PurchaseMaterialImage, 0, len(files))
	for i, f := range files {
		links = append(links, models.PurchaseMaterialImage{MaterialID: materialID, FileID: f.ID, SortOrder: i})
	}
	return tx.Create(&links).Error
}

// UpdatePurchaseMaterial 更新计划。
func UpdatePurchaseMaterial(db *gorm.DB, item *models.PurchaseMaterial, planDate *time.Time, materialCode, category, urgency, demandDepartment, name, modelSpec, unitName string, actualDemandPerson, purchaseResponsible *string, plannedQty decimal.Decimal, usage, subitemNo, remark string, stockMaterialID *int64, status *string, imageIDs []string, version int) (*models.PurchaseMaterial, *apperrors.AppError) {
	if appErr := ValidateVersion(version, item.Version); appErr != nil {
		return nil, appErr
	}
	responsible := ""
	if purchaseResponsible != nil {
		responsible = *purchaseResponsible
	}
	if responsible == "" {
		responsible = item.PurchaseResponsible
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
	item.MaterialCode = nilOr(materialCode)
	item.Category = nilOr(category)
	item.Urgency = urgency
	item.DemandDepartment = demandDepartment
	item.Name = name
	item.ModelSpec = modelSpec
	item.UnitName = unitName
	item.PlannedQty = models.Decimal{Decimal: plannedQty}
	item.Usage = usage
	item.SubitemNo = nilOr(subitemNo)
	item.Remark = nilOr(remark)
	item.StockMaterialID = stockMaterialID
	if actualDemandPerson != nil {
		item.ActualDemandPerson = *actualDemandPerson
	}
	item.PurchaseResponsible = responsible
	if status != nil {
		item.Status = *status
	}
	if planDate != nil && !planDate.Equal(item.PlanDate) {
		item.PlanDate = *planDate
		newNo, appErr := NextPurchasePlanNo(db, *planDate)
		if appErr != nil {
			return nil, appErr
		}
		item.PlanNo = newNo
	}
	item.Version++
	item.UpdatedAt = models.UTCNow()
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&item).Select("*").Updates(item).Error; err != nil {
			return err
		}
		return replacePurchaseMaterialImages(tx, item.ID, files)
	})
	if err != nil {
		return nil, DatabaseError(err)
	}
	return item, nil
}

// BatchUpdatePurchaseMaterials 批量更新。
func BatchUpdatePurchaseMaterials(db *gorm.DB, ids []int64, versions []int, planDate *time.Time, category, urgency, demandDepartment, actualDemandPerson, purchaseResponsible, subitemNo, usage, status *string) ([]models.PurchaseMaterial, *apperrors.AppError) {
	itemsByID := map[int64]*models.PurchaseMaterial{}
	var items []models.PurchaseMaterial
	if err := db.Where("id IN ?", ids).Find(&items).Error; err != nil {
		return nil, DatabaseError(err)
	}
	for i := range items {
		itemsByID[items[i].ID] = &items[i]
	}
	if len(itemsByID) != len(ids) {
		return nil, apperrors.NotFound("申购计划")
	}
	for i, id := range ids {
		item := itemsByID[id]
		if appErr := ValidateVersion(versions[i], item.Version); appErr != nil {
			return nil, appErr
		}
		if planDate != nil && !planDate.Equal(item.PlanDate) {
			newNo, appErr := NextPurchasePlanNo(db, *planDate)
			if appErr != nil {
				return nil, appErr
			}
			item.PlanNo = newNo
			item.PlanDate = *planDate
		}
		if category != nil {
			item.Category = nilOr(*category)
		}
		if urgency != nil {
			item.Urgency = *urgency
		}
		if demandDepartment != nil {
			item.DemandDepartment = *demandDepartment
		}
		if actualDemandPerson != nil {
			item.ActualDemandPerson = *actualDemandPerson
		}
		if purchaseResponsible != nil {
			item.PurchaseResponsible = *purchaseResponsible
		}
		if subitemNo != nil {
			item.SubitemNo = nilOr(*subitemNo)
		}
		if usage != nil {
			item.Usage = *usage
		}
		if status != nil {
			item.Status = *status
		}
		item.Version++
		item.UpdatedAt = models.UTCNow()
		if err := db.Model(item).Select("*").Updates(item).Error; err != nil {
			return nil, DatabaseError(err)
		}
	}
	return items, nil
}

// DeletePurchaseMaterial 删除计划（已转入则拒绝）。
func DeletePurchaseMaterial(db *gorm.DB, item *models.PurchaseMaterial, version int) *apperrors.AppError {
	if appErr := ValidateVersion(version, item.Version); appErr != nil {
		return appErr
	}
	var count int64
	db.Model(&models.PurchaseRequestLine{}).
		Where("purchase_material_id = ?", item.ID).Count(&count)
	if count > 0 {
		return apperrors.New("PURCHASE_PLAN_IN_USE", "已转入申购记录的计划不能删除", http.StatusConflict, nil)
	}
	if err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Delete(&models.PurchaseMaterialImage{}, "material_id = ?", item.ID).Error; err != nil {
			return err
		}
		return tx.Delete(&models.PurchaseMaterial{}, item.ID).Error
	}); err != nil {
		return DatabaseError(err)
	}
	return nil
}

// LinkStockMaterial 关联二级库物资。
func LinkStockMaterial(db *gorm.DB, item *models.PurchaseMaterial, stockMaterialID int64, version int) (*models.PurchaseMaterial, *apperrors.AppError) {
	if appErr := ValidateVersion(version, item.Version); appErr != nil {
		return nil, appErr
	}
	if _, err := GetStockMaterial(db, stockMaterialID); err != nil {
		return nil, err
	}
	item.StockMaterialID = &stockMaterialID
	item.Version++
	item.UpdatedAt = models.UTCNow()
	if err := db.Model(&item).Select("StockMaterialID", "Version", "UpdatedAt").Updates(item).Error; err != nil {
		return nil, DatabaseError(err)
	}
	return item, nil
}

// ============ 申购记录 ============

func usageHash(usage string) string {
	sum := sha256.Sum256([]byte(usage))
	return hex.EncodeToString(sum[:])[:32]
}

// DefaultPurchaseOrderNo 默认申购单号。
func DefaultPurchaseOrderNo() string {
	now := time.Now().In(ShanghaiTZ)
	return "申购 " + now.Format("2006/1/2")
}

// MovePlansToRecord 把计划转入申购记录（自包含快照）。
func MovePlansToRecord(db *gorm.DB, materialIDs []int64, purchaseOrderNo *string, contractNo, vesselNo, consolidationPort, traceNo, salesperson, status, recordRemark string, consolidationDate, sailingDate, purchaseDate *time.Time) ([]models.PurchaseRequestLine, *apperrors.AppError) {
	ids := dedupeIDs(materialIDs)
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	var materials []models.PurchaseMaterial
	if err := db.Where("id IN ?", ids).Order("id").Find(&materials).Error; err != nil {
		return nil, DatabaseError(err)
	}
	if len(materials) != len(ids) {
		return nil, apperrors.NotFound("申购计划")
	}
	var uncoded []int64
	for _, m := range materials {
		if m.MaterialCode == nil || *m.MaterialCode == "" {
			uncoded = append(uncoded, m.ID)
		}
	}
	if len(uncoded) > 0 {
		return nil, apperrors.New("MATERIAL_CODE_REQUIRED", "未编码物资不能转入申购记录",
			http.StatusConflict, map[string]any{"material_ids": uncoded})
	}
	var movedIDs []int64
	db.Model(&models.PurchaseRequestLine{}).
		Where("purchase_material_id IN ?", ids).Distinct().Pluck("purchase_material_id", &movedIDs)
	if len(movedIDs) > 0 {
		return nil, apperrors.New("PLAN_ALREADY_MOVED", "部分申购计划已转入申购记录",
			http.StatusConflict, map[string]any{"material_ids": movedIDs})
	}
	orderNo := DefaultPurchaseOrderNo()
	if purchaseOrderNo != nil {
		orderNo = *purchaseOrderNo
	}
	request := models.PurchaseRequest{
		PurchaseOrderNo:   &orderNo,
		ContractNo:        nilOr(contractNo),
		VesselNo:          nilOr(vesselNo),
		ConsolidationDate: consolidationDate,
		ConsolidationPort: nilOr(consolidationPort),
		SailingDate:       sailingDate,
		Remark:            nilOr(recordRemark),
		PurchaseDate:      purchaseDate,
	}
	if status == "" {
		status = "已申购"
	}
	var lines []models.PurchaseRequestLine
	for i := range materials {
		m := materials[i]
		line := models.PurchaseRequestLine{
			PurchaseMaterialID:          &m.ID,
			PlanNoSnapshot:              m.PlanNo,
			PlanDateSnapshot:            m.PlanDate,
			MaterialCodeSnapshot:        m.MaterialCode,
			CategorySnapshot:            m.Category,
			DemandDepartmentSnapshot:    m.DemandDepartment,
			MaterialNameSnapshot:        m.Name,
			ModelSpecSnapshot:           m.ModelSpec,
			UnitNameSnapshot:            m.UnitName,
			ActualDemandPersonSnapshot:  m.ActualDemandPerson,
			PurchaseResponsibleSnapshot: m.PurchaseResponsible,
			PlanRemarkSnapshot:          m.Remark,
			StockMaterialIDSnapshot:     m.StockMaterialID,
			PurchaseQty:                 m.PlannedQty,
			Status:                      status,
			Usage:                       m.Usage,
			UsageHash:                   usageHash(m.Usage),
			SubitemNo:                   m.SubitemNo,
			TraceNo:                     nilOr(traceNo),
			Salesperson:                 nilOr(salesperson),
		}
		lines = append(lines, line)
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(&request).Error; err != nil {
			return err
		}
		// 复制计划图片引用到记录行
		var materialImageLinks []models.PurchaseMaterialImage
		if err := tx.Where("material_id IN ?", ids).Order("material_id, sort_order").
			Find(&materialImageLinks).Error; err != nil {
			return err
		}
		byMaterial := map[int64][]models.PurchaseMaterialImage{}
		for _, l := range materialImageLinks {
			byMaterial[l.MaterialID] = append(byMaterial[l.MaterialID], l)
		}
		for i := range lines {
			lines[i].PurchaseRequestID = request.ID
		}
		if err := tx.Create(&lines).Error; err != nil {
			return err
		}
		var lineImages []models.PurchaseRequestLineImage
		for i := range lines {
			links := byMaterial[materialIDs[i]]
			for j, l := range links {
				lineImages = append(lineImages, models.PurchaseRequestLineImage{
					LineID: lines[i].ID, FileID: l.FileID, SortOrder: j,
				})
			}
		}
		if len(lineImages) > 0 {
			if err := tx.Create(&lineImages).Error; err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		if database.IsDuplicateError(err) {
			return nil, apperrors.New("DATA_CONFLICT", "数据约束冲突", http.StatusConflict, nil)
		}
		return nil, DatabaseError(err)
	}
	// 计划状态归档
	db.Model(&models.PurchaseMaterial{}).Where("id IN ?", ids).
		Updates(map[string]any{"status": domain.PlanArchived})
	return lines, nil
}

// GetPurchaseRecord 查询记录行。
func GetPurchaseRecord(db *gorm.DB, lineID int64, forUpdate bool) (*models.PurchaseRequestLine, *apperrors.AppError) {
	q := db.Where("id = ?", lineID)
	if forUpdate {
		q = q.Clauses(clause.Locking{Strength: "UPDATE"})
	}
	var line models.PurchaseRequestLine
	err := q.First(&line).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("申购记录")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	_ = db.Where("id = ?", line.PurchaseRequestID).First(&line.Request).Error
	_ = db.Where("line_id = ?", line.ID).Order("sort_order").Find(&line.Images).Error
	return &line, nil
}

// PurchaseRecordReadData 记录 read 关联数据。
type PurchaseRecordReadData struct {
	Images []models.FileObject
}

// LoadRecordImages 记录行图片。
func LoadRecordImages(db *gorm.DB, lineID int64) ([]models.FileObject, *apperrors.AppError) {
	var links []models.PurchaseRequestLineImage
	if err := db.Where("line_id = ?", lineID).Order("sort_order").Find(&links).Error; err != nil {
		return nil, DatabaseError(err)
	}
	var out []models.FileObject
	if len(links) == 0 {
		return out, nil
	}
	fileIDs := make([]string, 0, len(links))
	for _, l := range links {
		fileIDs = append(fileIDs, l.FileID)
	}
	var files []models.FileObject
	if err := db.Where("id IN ?", fileIDs).Find(&files).Error; err != nil {
		return nil, DatabaseError(err)
	}
	byID := map[string]models.FileObject{}
	for _, f := range files {
		byID[f.ID] = f
	}
	for _, l := range links {
		if f, ok := byID[l.FileID]; ok {
			out = append(out, f)
		}
	}
	return out, nil
}

// SearchPurchaseRecords 记录列表。
func SearchPurchaseRecords(db *gorm.DB, status string, emptyStatus bool, keyword, searchField, searchValue, purchaseOrderNo, traceNo, category, name, modelSpec, actualDemandPerson, purchaseResponsible, salesperson, subitemNo string, emptySubitemNo bool, page, pageSize int, sortBy, sortOrder string) ([]models.PurchaseRequestLine, int, *apperrors.AppError) {
	q := db.Model(&models.PurchaseRequestLine{}).
		Joins("JOIN purchase_request ON purchase_request.id = purchase_request_line.purchase_request_id")
	if status != "" {
		q = q.Where("purchase_request_line.status = ?", status)
	} else if emptyStatus {
		q = q.Where("(purchase_request_line.status IS NULL OR TRIM(purchase_request_line.status) = '')")
	}
	if clause, args := ContainsAnyClause([]string{
		"purchase_request_line.plan_no_snapshot", "CAST(purchase_request_line.plan_date_snapshot AS CHAR)",
		"purchase_request_line.material_name_snapshot", "purchase_request_line.model_spec_snapshot",
		"purchase_request_line.material_code_snapshot", "purchase_request_line.usage",
		"purchase_request_line.trace_no", "purchase_request.purchase_order_no",
		"purchase_request_line.actual_demand_person_snapshot", "purchase_request_line.purchase_responsible_snapshot",
	}, keyword); clause != "" {
		q = q.Where(clause, args...)
	}
	if purchaseOrderNo != "" {
		if clause, args := ContainsAnyClause([]string{"purchase_request.purchase_order_no"}, purchaseOrderNo); clause != "" {
			q = q.Where(clause, args...)
		}
	}
	if traceNo != "" {
		if clause, args := ContainsAnyClause([]string{"purchase_request_line.trace_no"}, traceNo); clause != "" {
			q = q.Where(clause, args...)
		}
	}
	if category != "" {
		q = q.Where("purchase_request_line.category_snapshot = ?", category)
	}
	if clause, args := ContainsAnyClause([]string{"purchase_request_line.material_name_snapshot"}, name); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"purchase_request_line.model_spec_snapshot"}, modelSpec); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"purchase_request_line.actual_demand_person_snapshot"}, actualDemandPerson); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"purchase_request_line.purchase_responsible_snapshot"}, purchaseResponsible); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"purchase_request_line.salesperson"}, salesperson); clause != "" {
		q = q.Where(clause, args...)
	}
	if emptySubitemNo {
		q = q.Where("(purchase_request_line.subitem_no IS NULL OR TRIM(purchase_request_line.subitem_no) = '')")
	} else if subitemNo != "" {
		q = q.Where("TRIM(purchase_request_line.subitem_no) = ?", strings.TrimSpace(subitemNo))
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	orderCol := ""
	switch sortBy {
	case "plan_no", "plan_date", "purchase_order_no", "trace_no", "contract_no", "vessel_no",
		"consolidation_date", "consolidation_port", "sailing_date", "category", "material_code",
		"material_name", "model_spec", "unit_name", "purchase_qty", "salesperson", "status",
		"purchase_date", "usage", "subitem_no", "plan_remark", "record_remark":
		orderCol = sortBy
	}
	if orderCol != "" {
		dir := "DESC"
		if sortOrder == "asc" {
			dir = "ASC"
		}
		q = q.Order(orderCol + " " + dir).Order("purchase_request_line.id DESC")
	} else {
		q = q.Order("purchase_request_line.id DESC")
	}
	var lines []models.PurchaseRequestLine
	if err := q.Select("purchase_request_line.*").Offset((page - 1) * pageSize).Limit(pageSize).
		Find(&lines).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	// 载入 request 与图片
	for i := range lines {
		db.Where("id = ?", lines[i].PurchaseRequestID).First(&lines[i].Request)
		imgs, _ := LoadRecordImages(db, lines[i].ID)
		lines[i].Images = make([]models.PurchaseRequestLineImage, 0, len(imgs))
		for _, f := range imgs {
			lines[i].Images = append(lines[i].Images, models.PurchaseRequestLineImage{FileID: f.ID})
		}
	}
	return lines, int(total), nil
}

// UpdatePurchaseRecord 更新记录行。
func UpdatePurchaseRecord(db *gorm.DB, line *models.PurchaseRequestLine, req *models.PurchaseRequest, planDate time.Time, materialCode, category, demandDepartment, materialName, modelSpec, unitName, actualDemandPerson, purchaseResponsible string, purchaseQty decimal.Decimal, usage, subitemNo, salesperson, status string, imageIDs []string, version int) (*models.PurchaseRequestLine, *apperrors.AppError) {
	if appErr := ValidateVersion(version, req.Version); appErr != nil {
		return nil, appErr
	}
	files, appErr := ValidateImageIDs(db, imageIDs)
	if appErr != nil {
		return nil, appErr
	}
	req.Version++
	req.UpdatedAt = models.UTCNow()
	line.PlanDateSnapshot = planDate
	line.MaterialCodeSnapshot = nilOr(materialCode)
	line.CategorySnapshot = nilOr(category)
	line.DemandDepartmentSnapshot = demandDepartment
	line.MaterialNameSnapshot = materialName
	line.ModelSpecSnapshot = modelSpec
	line.UnitNameSnapshot = unitName
	line.ActualDemandPersonSnapshot = actualDemandPerson
	line.PurchaseResponsibleSnapshot = purchaseResponsible
	line.PurchaseQty = models.Decimal{Decimal: purchaseQty}
	line.Status = status
	line.Usage = usage
	line.UsageHash = usageHash(usage)
	line.SubitemNo = nilOr(subitemNo)
	line.Salesperson = nilOr(salesperson)
	line.Version++
	line.UpdatedAt = models.UTCNow()
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(req).Select("Version", "UpdatedAt").Updates(req).Error; err != nil {
			return err
		}
		if err := tx.Model(line).Select("*").Updates(line).Error; err != nil {
			return err
		}
		if err := tx.Delete(&models.PurchaseRequestLineImage{}, "line_id = ?", line.ID).Error; err != nil {
			return err
		}
		if len(files) > 0 {
			links := make([]models.PurchaseRequestLineImage, 0, len(files))
			for i, f := range files {
				links = append(links, models.PurchaseRequestLineImage{LineID: line.ID, FileID: f.ID, SortOrder: i})
			}
			return tx.Create(&links).Error
		}
		return nil
	})
	if err != nil {
		return nil, DatabaseError(err)
	}
	return line, nil
}

// RestorePurchaseRecordToPlan 记录回撤为计划。
func RestorePurchaseRecordToPlan(db *gorm.DB, line *models.PurchaseRequestLine, version int) (*models.PurchaseMaterial, *apperrors.AppError) {
	if appErr := ValidateVersion(version, line.Version); appErr != nil {
		return nil, appErr
	}
	planDate := time.Now().In(ShanghaiTZ)
	planNo, appErr := NextPurchasePlanNo(db, planDate)
	if appErr != nil {
		return nil, appErr
	}
	material := models.PurchaseMaterial{
		PlanNo:              planNo,
		PlanDate:            planDate,
		MaterialCode:        line.MaterialCodeSnapshot,
		Category:            line.CategorySnapshot,
		Urgency:             "正常",
		DemandDepartment:    line.DemandDepartmentSnapshot,
		Name:                line.MaterialNameSnapshot,
		ModelSpec:           line.ModelSpecSnapshot,
		UnitName:            line.UnitNameSnapshot,
		ActualDemandPerson:  line.ActualDemandPersonSnapshot,
		PurchaseResponsible: line.PurchaseResponsibleSnapshot,
		PlannedQty:          line.PurchaseQty,
		Usage:               line.Usage,
		SubitemNo:           line.SubitemNo,
		Remark:              line.PlanRemarkSnapshot,
		StockMaterialID:     line.StockMaterialIDSnapshot,
		Status:              domain.PlanNormal,
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(&material).Error; err != nil {
			return err
		}
		var links []models.PurchaseRequestLineImage
		if err := tx.Where("line_id = ?", line.ID).Find(&links).Error; err != nil {
			return err
		}
		if len(links) > 0 {
			imgs := make([]models.PurchaseMaterialImage, 0, len(links))
			for i, l := range links {
				imgs = append(imgs, models.PurchaseMaterialImage{MaterialID: material.ID, FileID: l.FileID, SortOrder: i})
			}
			if err := tx.Create(&imgs).Error; err != nil {
				return err
			}
		}
		return tx.Delete(&models.PurchaseRequestLine{}, line.ID).Error
	})
	if err != nil {
		return nil, DatabaseError(err)
	}
	return &material, nil
}

// ============ 计划模板 ============

func LoadTemplateDetail(db *gorm.DB, templateID int64) (*models.PurchasePlanTemplate, *apperrors.AppError) {
	var tpl models.PurchasePlanTemplate
	err := db.First(&tpl, templateID).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("周期性计划")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	return &tpl, nil
}

// SearchTemplates 模板列表。
func SearchTemplates(db *gorm.DB, keyword, name, modelSpec, actualDemandPerson, purchaseResponsible, category string, page, pageSize int, sortBy, sortOrder string) ([]models.PurchasePlanTemplate, int, *apperrors.AppError) {
	q := db.Model(&models.PurchasePlanTemplate{})
	if clause, args := ContainsAnyClause([]string{
		"name", "model_spec", "material_code", "category", "unit_name", "usage", "subitem_no", "remark",
	}, keyword); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"name"}, name); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"model_spec"}, modelSpec); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"actual_demand_person"}, actualDemandPerson); clause != "" {
		q = q.Where(clause, args...)
	}
	if clause, args := ContainsAnyClause([]string{"purchase_responsible"}, purchaseResponsible); clause != "" {
		q = q.Where(clause, args...)
	}
	if category != "" {
		q = q.Where("TRIM(category) = ?", strings.TrimSpace(category))
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	q = q.Order("id DESC")
	var items []models.PurchasePlanTemplate
	if err := q.Offset((page - 1) * pageSize).Limit(pageSize).Find(&items).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	return items, int(total), nil
}

// TemplateFilterOptions 模板筛选下拉。
func TemplateFilterOptions(db *gorm.DB) ([]string, []string, []string, *apperrors.AppError) {
	var persons, responsibles, categories []*string
	build := func() *gorm.DB { return db.Model(&models.PurchasePlanTemplate{}) }
	if err := build().Distinct().Order("actual_demand_person").Pluck("actual_demand_person", &persons).Error; err != nil {
		return nil, nil, nil, DatabaseError(err)
	}
	if err := build().Distinct().Order("purchase_responsible").Pluck("purchase_responsible", &responsibles).Error; err != nil {
		return nil, nil, nil, DatabaseError(err)
	}
	if err := build().Distinct().Order("category").Pluck("category", &categories).Error; err != nil {
		return nil, nil, nil, DatabaseError(err)
	}
	return derefNonEmpty(persons), derefNonEmpty(responsibles), derefNonEmpty(categories), nil
}

// CreateTemplate 创建模板。
func CreateTemplate(db *gorm.DB, materialCode, category, urgency, demandDepartment, name, modelSpec, unitName string, actualDemandPerson, purchaseResponsible *string, plannedQty decimal.Decimal, usage, subitemNo, remark string, stockMaterialID *int64, imageIDs []string) (*models.PurchasePlanTemplate, *apperrors.AppError) {
	responsible := ""
	if purchaseResponsible != nil {
		responsible = *purchaseResponsible
	}
	if responsible == "" {
		responsible = "\\"
	}
	person := ""
	if actualDemandPerson != nil {
		person = *actualDemandPerson
	}
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
	tpl := models.PurchasePlanTemplate{
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
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Create(&tpl).Error; err != nil {
			return err
		}
		if len(files) == 0 {
			return nil
		}
		links := make([]models.PurchasePlanTemplateImage, 0, len(files))
		for i, f := range files {
			links = append(links, models.PurchasePlanTemplateImage{PlanID: tpl.ID, FileID: f.ID, SortOrder: i})
		}
		return tx.Create(&links).Error
	})
	if err != nil {
		return nil, DatabaseError(err)
	}
	return &tpl, nil
}

// UpdateTemplate 更新模板。
func UpdateTemplate(db *gorm.DB, tpl *models.PurchasePlanTemplate, materialCode, category, urgency, demandDepartment, name, modelSpec, unitName string, actualDemandPerson, purchaseResponsible *string, plannedQty decimal.Decimal, usage, subitemNo, remark string, stockMaterialID *int64, imageIDs []string, version int) (*models.PurchasePlanTemplate, *apperrors.AppError) {
	if appErr := ValidateVersion(version, tpl.Version); appErr != nil {
		return nil, appErr
	}
	responsible := ""
	if purchaseResponsible != nil {
		responsible = *purchaseResponsible
	}
	if responsible == "" {
		responsible = tpl.PurchaseResponsible
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
	tpl.MaterialCode = nilOr(materialCode)
	tpl.Category = nilOr(category)
	tpl.Urgency = urgency
	tpl.DemandDepartment = demandDepartment
	tpl.Name = name
	tpl.ModelSpec = modelSpec
	tpl.UnitName = unitName
	tpl.PlannedQty = models.Decimal{Decimal: plannedQty}
	tpl.Usage = usage
	tpl.SubitemNo = nilOr(subitemNo)
	tpl.Remark = nilOr(remark)
	tpl.StockMaterialID = stockMaterialID
	if actualDemandPerson != nil {
		tpl.ActualDemandPerson = *actualDemandPerson
	}
	tpl.PurchaseResponsible = responsible
	tpl.Version++
	tpl.UpdatedAt = models.UTCNow()
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(tpl).Select("*").Updates(tpl).Error; err != nil {
			return err
		}
		if err := tx.Delete(&models.PurchasePlanTemplateImage{}, "plan_id = ?", tpl.ID).Error; err != nil {
			return err
		}
		if len(files) == 0 {
			return nil
		}
		links := make([]models.PurchasePlanTemplateImage, 0, len(files))
		for i, f := range files {
			links = append(links, models.PurchasePlanTemplateImage{PlanID: tpl.ID, FileID: f.ID, SortOrder: i})
		}
		return tx.Create(&links).Error
	})
	if err != nil {
		return nil, DatabaseError(err)
	}
	return tpl, nil
}

// DeleteTemplate 删除模板。
func DeleteTemplate(db *gorm.DB, tpl *models.PurchasePlanTemplate, version int) *apperrors.AppError {
	if appErr := ValidateVersion(version, tpl.Version); appErr != nil {
		return appErr
	}
	if err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Delete(&models.PurchasePlanTemplateImage{}, "plan_id = ?", tpl.ID).Error; err != nil {
			return err
		}
		return tx.Delete(&models.PurchasePlanTemplate{}, tpl.ID).Error
	}); err != nil {
		return DatabaseError(err)
	}
	return nil
}

// GeneratePurchasePlanFromTemplate 模板生成计划。
func GeneratePurchasePlanFromTemplate(db *gorm.DB, tpl *models.PurchasePlanTemplate) (*models.PurchaseMaterial, *apperrors.AppError) {
	today := time.Now().In(ShanghaiTZ)
	planNo, appErr := NextPurchasePlanNo(db, today)
	if appErr != nil {
		return nil, appErr
	}
	var links []models.PurchasePlanTemplateImage
	_ = db.Where("plan_id = ?", tpl.ID).Order("sort_order").Find(&links).Error
	imageIDs := make([]string, 0, len(links))
	for _, l := range links {
		imageIDs = append(imageIDs, l.FileID)
	}
	person := tpl.ActualDemandPerson
	return CreatePurchaseMaterialFull(db, &today, deref(tpl.MaterialCode), deref(tpl.Category), tpl.Urgency,
		tpl.DemandDepartment, tpl.Name, tpl.ModelSpec, tpl.UnitName, &person, &tpl.PurchaseResponsible,
		tpl.PlannedQty.Decimal, tpl.Usage, deref(tpl.SubitemNo), deref(tpl.Remark),
		tpl.StockMaterialID, domain.PlanNormal, planNo, imageIDs)
}

func deref(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// ============ 分享链接 ============

func durPtr(d time.Duration) *time.Duration { return &d }

var shareExpiryDeltas = map[string]*time.Duration{
	"24h": durPtr(24 * time.Hour), "3d": durPtr(3 * 24 * time.Hour),
	"7d": durPtr(7 * 24 * time.Hour), "30d": durPtr(30 * 24 * time.Hour), "permanent": nil,
}

var shareTypeLabel = map[string]string{
	domain.SharePurchasePlan: "申购计划", domain.SharePurchaseRecord: "申购记录",
}

var sharePlanKeys = map[string]bool{
	"plan_date": true, "material_code": true, "category": true, "urgency": true,
	"demand_department": true, "name": true, "model_spec": true, "planned_qty": true,
	"actual_demand_person": true, "purchase_responsible": true, "subitem_no": true,
	"usage": true, "status": true, "images": true,
}

var shareRecordKeys = map[string]bool{
	"plan_date": true, "purchase_order_no": true, "trace_no": true, "category": true,
	"demand_department": true, "material_name": true, "model_spec": true, "purchase_qty": true,
	"actual_demand_person": true, "purchase_responsible": true, "salesperson": true,
	"subitem_no": true, "usage": true, "status": true, "images": true,
}

// ShareTypeValue 把 DB 存的枚举名（如 PURCHASE_PLAN）转为 API 值（purchase_plan）；值本身则原样。
func ShareTypeValue(name string) string {
	if name == domain.SharePurchasePlan || name == domain.SharePurchaseRecord {
		return name
	}
	return strings.ToLower(name)
}

// shareTypeValue 把 DB 存的枚举名（如 PURCHASE_PLAN）转为 API 值（purchase_plan）；值本身则原样。
func shareTypeValue(name string) string {
	if name == domain.SharePurchasePlan || name == domain.SharePurchaseRecord {
		return name
	}
	return strings.ToLower(name)
}

// shareTypeName 把 API 值转 DB 枚举名（MySQL ENUM 存大写名）。
func shareTypeName(value string) string {
	return strings.ToUpper(value)
}

func shareAllowedKeys(shareType string) map[string]bool {
	if shareType == domain.SharePurchasePlan {
		return sharePlanKeys
	}
	return shareRecordKeys
}

func validateShareColumns(shareType string, columns []string) *apperrors.AppError {
	allowed := shareAllowedKeys(shareType)
	for _, key := range columns {
		if !allowed[key] {
			return apperrors.New("VALIDATION_ERROR",
				"包含不适用于"+shareTypeLabel[shareType]+"的列: "+key, 422, nil)
		}
	}
	return nil
}

// CreateShare 创建分享链接。
func CreateShare(db *gorm.DB, shareType string, itemIDs []int64, expiresIn string, createdBy int64, columns []string) (*models.ShareLink, *apperrors.AppError) {
	ids := dedupeIDs(itemIDs)
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	if shareType == domain.SharePurchasePlan {
		var count int64
		db.Model(&models.PurchaseMaterial{}).Where("id IN ?", ids).Count(&count)
		if int(count) != len(ids) {
			return nil, apperrors.NotFound(shareTypeLabel[shareType])
		}
	} else {
		var count int64
		db.Model(&models.PurchaseRequestLine{}).Where("id IN ?", ids).Count(&count)
		if int(count) != len(ids) {
			return nil, apperrors.NotFound(shareTypeLabel[shareType])
		}
	}
	if appErr := validateShareColumns(shareType, columns); appErr != nil {
		return nil, appErr
	}
	var expiresAt *time.Time
	if delta := shareExpiryDeltas[expiresIn]; delta != nil {
		t := models.UTCNow().Add(*delta)
		expiresAt = &t
	}
	var columnsJSON models.JSON
	if columns != nil {
		columnsJSON = mustJSON(columns)
	}
	share := models.ShareLink{
		Token:     security.UUID7String(),
		ShareType: shareTypeName(shareType),
		ItemIDs:   mustJSON(ids),
		Columns:   columnsJSON,
		ExpiresAt: expiresAt,
		CreatedBy: &createdBy,
		CreatedAt: models.UTCNow(),
		UpdatedAt: models.UTCNow(),
	}
	if err := db.Create(&share).Error; err != nil {
		return nil, DatabaseError(err)
	}
	return &share, nil
}

// ListShares 分享列表。
func ListShares(db *gorm.DB, userID int64, isSuper bool, page, pageSize int) ([]models.ShareLink, []*string, int, *apperrors.AppError) {
	q := db.Model(&models.ShareLink{})
	if !isSuper {
		q = q.Where("created_by = ?", userID)
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, nil, 0, DatabaseError(err)
	}
	var shares []models.ShareLink
	if err := q.Order("id DESC").Offset((page - 1) * pageSize).Limit(pageSize).Find(&shares).Error; err != nil {
		return nil, nil, 0, DatabaseError(err)
	}
	names := make([]*string, len(shares))
	for i, s := range shares {
		if s.CreatedBy != nil {
			var u models.User
			if err := db.Select("display_name").First(&u, *s.CreatedBy).Error; err == nil {
				name := u.DisplayName
				names[i] = &name
			}
		}
	}
	return shares, names, int(total), nil
}

// GetPublicShare 匿名读取分享。
func GetPublicShare(db *gorm.DB, token string) (*models.ShareLink, map[string]any, *apperrors.AppError) {
	var share models.ShareLink
	err := db.Where("token = ?", token).First(&share).Error
	if IsNotFound(err) {
		return nil, nil, apperrors.New("SHARE_NOT_FOUND", "分享链接不存在或已失效", 400, nil)
	}
	if err != nil {
		return nil, nil, DatabaseError(err)
	}
	if share.ExpiresAt != nil && share.ExpiresAt.Before(models.UTCNow()) {
		return nil, nil, apperrors.New("SHARE_EXPIRED", "分享链接已失效，请联系分享人重新分享", 400, nil)
	}
	var ids []int64
	_ = jsonUnmarshal(share.ItemIDs, &ids)
	// 组装 items（实时快照）
	storedType := shareTypeValue(share.ShareType)
	var items []map[string]any
	if storedType == domain.SharePurchasePlan {
		var materials []models.PurchaseMaterial
		db.Where("id IN ?", ids).Find(&materials)
		byID := map[int64]models.PurchaseMaterial{}
		for _, m := range materials {
			byID[m.ID] = m
		}
		for _, id := range ids {
			if m, ok := byID[id]; ok {
				items = append(items, sharePlanItem(db, &m))
			}
		}
	} else {
		var lines []models.PurchaseRequestLine
		db.Where("id IN ?", ids).Find(&lines)
		byID := map[int64]models.PurchaseRequestLine{}
		for _, l := range lines {
			byID[l.ID] = l
		}
		for _, id := range ids {
			if l, ok := byID[id]; ok {
				items = append(items, shareRecordItem(db, &l))
			}
		}
	}
	return &share, map[string]any{"items": items}, nil
}

func sharePlanItem(db *gorm.DB, m *models.PurchaseMaterial) map[string]any {
	return map[string]any{
		"id": m.ID, "plan_no": m.PlanNo, "plan_date": serialize.FormatDate(m.PlanDate),
		"material_code": m.MaterialCode, "category": m.Category, "urgency": m.Urgency,
		"demand_department": m.DemandDepartment, "name": m.Name, "model_spec": m.ModelSpec,
		"unit_name": m.UnitName, "planned_qty": serialize.DecimalToString(m.PlannedQty.Decimal),
		"actual_demand_person": m.ActualDemandPerson, "purchase_responsible": m.PurchaseResponsible,
		"subitem_no": m.SubitemNo, "usage": m.Usage, "remark": m.Remark,
		"status": domain.PlanStatusValue[m.Status],
	}
}

func shareRecordItem(db *gorm.DB, l *models.PurchaseRequestLine) map[string]any {
	return map[string]any{
		"id": l.ID, "plan_no": l.PlanNoSnapshot, "plan_date": serialize.FormatDate(l.PlanDateSnapshot),
		"material_code": l.MaterialCodeSnapshot, "category": l.CategorySnapshot,
		"demand_department": l.DemandDepartmentSnapshot, "material_name": l.MaterialNameSnapshot,
		"model_spec": l.ModelSpecSnapshot, "unit_name": l.UnitNameSnapshot,
		"purchase_qty":         serialize.DecimalToString(l.PurchaseQty.Decimal),
		"actual_demand_person": l.ActualDemandPersonSnapshot,
		"purchase_responsible": l.PurchaseResponsibleSnapshot,
		"subitem_no":           l.SubitemNo, "usage": l.Usage, "status": l.Status,
	}
}

// UpdateShare 编辑分享（仅创建者或超管）。
func UpdateShare(db *gorm.DB, token string, userID int64, isSuper bool, columns []string, expiresIn *string) (*models.ShareLink, *apperrors.AppError) {
	var share models.ShareLink
	err := db.Where("token = ?", token).First(&share).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("分享链接")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	if !isSuper && (share.CreatedBy == nil || *share.CreatedBy != userID) {
		return nil, apperrors.New("FORBIDDEN", "没有执行此操作的权限", 403, nil)
	}
	if appErr := validateShareColumns(shareTypeValue(share.ShareType), columns); appErr != nil {
		return nil, appErr
	}
	updates := map[string]any{"columns": mustJSON(columns), "updated_at": models.UTCNow()}
	if expiresIn != nil {
		if delta := shareExpiryDeltas[*expiresIn]; delta != nil {
			t := models.UTCNow().Add(*delta)
			updates["expires_at"] = t
		} else {
			updates["expires_at"] = nil
		}
	}
	if err := db.Model(&models.ShareLink{}).Where("token = ?", token).Updates(updates).Error; err != nil {
		return nil, DatabaseError(err)
	}
	if err := db.Where("token = ?", token).First(&share).Error; err != nil {
		return nil, DatabaseError(err)
	}
	return &share, nil
}

// RevokeShare 撤回分享。
func RevokeShare(db *gorm.DB, token string, userID int64, isSuper bool) *apperrors.AppError {
	var share models.ShareLink
	err := db.Where("token = ?", token).First(&share).Error
	if IsNotFound(err) {
		return apperrors.NotFound("分享链接")
	}
	if err != nil {
		return DatabaseError(err)
	}
	if !isSuper && (share.CreatedBy == nil || *share.CreatedBy != userID) {
		return apperrors.New("FORBIDDEN", "没有执行此操作的权限", 403, nil)
	}
	if err := db.Delete(&models.ShareLink{}, "token = ?", token).Error; err != nil {
		return DatabaseError(err)
	}
	return nil
}

// CleanupExpiredShares 清理过期分享。
func CleanupExpiredShares(db *gorm.DB) int {
	res := db.Where("expires_at IS NOT NULL AND expires_at < ?", models.UTCNow()).
		Delete(&models.ShareLink{})
	if res.Error != nil {
		return 0
	}
	return int(res.RowsAffected)
}

func jsonUnmarshal(data models.JSON, dst any) error {
	return json.Unmarshal(data, dst)
}

// RecordFilterOptions 记录筛选下拉：业务员/状态 distinct。
func RecordFilterOptions(db *gorm.DB) ([]string, []string, *apperrors.AppError) {
	var salespersons, statuses []string
	if err := db.Model(&models.PurchaseRequestLine{}).
		Where("salesperson IS NOT NULL AND TRIM(salesperson) != ''").
		Distinct().Order("salesperson").Pluck("salesperson", &salespersons).Error; err != nil {
		return nil, nil, DatabaseError(err)
	}
	if err := db.Model(&models.PurchaseRequestLine{}).
		Where("status IS NOT NULL AND TRIM(status) != ''").
		Distinct().Order("status").Pluck("status", &statuses).Error; err != nil {
		return nil, nil, DatabaseError(err)
	}
	return salespersons, statuses, nil
}

// BatchUpdatePurchaseRecords 批量更新记录行头部字段。
func BatchUpdatePurchaseRecords(db *gorm.DB, lineIDs []int64, versions []int, purchaseOrderNo, contractNo, vesselNo, consolidationPort, salesperson, status *string, consolidationDate, sailingDate, purchaseDate *time.Time) ([]models.PurchaseRequestLine, *apperrors.AppError) {
	var lines []models.PurchaseRequestLine
	if err := db.Where("id IN ?", lineIDs).Find(&lines).Error; err != nil {
		return nil, DatabaseError(err)
	}
	byID := map[int64]*models.PurchaseRequestLine{}
	for i := range lines {
		byID[lines[i].ID] = &lines[i]
	}
	if len(byID) != len(lineIDs) {
		return nil, apperrors.NotFound("申购记录")
	}
	for i, id := range lineIDs {
		line := byID[id]
		if appErr := ValidateVersion(versions[i], line.Version); appErr != nil {
			return nil, appErr
		}
		var req models.PurchaseRequest
		if err := db.Where("id = ?", line.PurchaseRequestID).First(&req).Error; err != nil {
			return nil, DatabaseError(err)
		}
		if purchaseOrderNo != nil {
			v := *purchaseOrderNo
			req.PurchaseOrderNo = &v
		}
		if contractNo != nil {
			req.ContractNo = nilOr(*contractNo)
		}
		if vesselNo != nil {
			req.VesselNo = nilOr(*vesselNo)
		}
		if consolidationPort != nil {
			req.ConsolidationPort = nilOr(*consolidationPort)
		}
		if consolidationDate != nil {
			req.ConsolidationDate = consolidationDate
		}
		if sailingDate != nil {
			req.SailingDate = sailingDate
		}
		if purchaseDate != nil {
			req.PurchaseDate = purchaseDate
		}
		if salesperson != nil {
			line.Salesperson = nilOr(*salesperson)
		}
		if status != nil {
			line.Status = *status
		}
		req.Version++
		req.UpdatedAt = models.UTCNow()
		line.Version++
		line.UpdatedAt = models.UTCNow()
		if err := db.Model(&req).Select("Version", "UpdatedAt", "PurchaseOrderNo", "ContractNo", "VesselNo", "ConsolidationPort", "ConsolidationDate", "SailingDate", "PurchaseDate").Updates(req).Error; err != nil {
			return nil, DatabaseError(err)
		}
		if err := db.Model(line).Select("Version", "UpdatedAt", "Salesperson", "Status").Updates(line).Error; err != nil {
			return nil, DatabaseError(err)
		}
	}
	return lines, nil
}

// ============ 申购记录同步 ============

var syncFields = map[string]bool{
	"salesperson": true, "contract_no": true, "vessel_no": true, "consolidation_port": true,
	"consolidation_date": true, "sailing_date": true, "status": true,
}

var statusProgression = map[string][]string{
	"已入库":  {"已申购", "已采购", "部分入库", "已入库"},
	"部分入库": {"已申购", "已采购", "部分入库"},
	"已采购":  {"已申购", "已采购"},
}

// ListSyncTargets 待同步目标列表（按 trace_no 分组）。
func ListSyncTargets(db *gorm.DB, limit, cursor int, fields, minPO string) ([]dto.PurchaseRecordSyncTargetRead, bool, int64, *apperrors.AppError) {
	activeFields := map[string]bool(nil)
	if fields != "" {
		parsed := map[string]bool{}
		for _, part := range strings.Split(fields, ",") {
			p := strings.TrimSpace(part)
			if p == "" {
				continue
			}
			if !syncFields[p] {
				return nil, false, 0, apperrors.New("VALIDATION_ERROR",
					"未知同步字段: "+p, 422, nil)
			}
			parsed[p] = true
		}
		activeFields = parsed
	}
	_ = activeFields
	q := db.Model(&models.PurchaseRequestLine{}).
		Select("trace_no, COUNT(*) AS count, MAX(id) AS cursor_id").
		Where("trace_no IS NOT NULL AND TRIM(trace_no) != ''")
	if cursor > 0 {
		q = q.Where("id > ?", cursor)
	}
	if minPO != "" {
		if len(minPO) > 128 {
			return nil, false, 0, apperrors.New("VALIDATION_ERROR", "申购单号起始值过长", 422, nil)
		}
		q = q.Joins("JOIN purchase_request ON purchase_request.id = purchase_request_line.purchase_request_id").
			Where("purchase_request.purchase_order_no >= ?", minPO)
	}
	q = q.Group("trace_no").Order("cursor_id").Limit(limit + 1)
	type row struct {
		TraceNo  string
		Count    int
		CursorID int64
	}
	var rows []row
	if err := q.Scan(&rows).Error; err != nil {
		return nil, false, 0, DatabaseError(err)
	}
	hasMore := len(rows) > limit
	if hasMore {
		rows = rows[:limit]
	}
	var items []dto.PurchaseRecordSyncTargetRead
	next := int64(0)
	if len(rows) > 0 {
		for _, r := range rows {
			items = append(items, dto.PurchaseRecordSyncTargetRead{
				TraceNo: r.TraceNo, TargetCount: r.Count, CursorID: r.CursorID,
			})
			next = r.CursorID
		}
	}
	return items, hasMore, next, nil
}

// ApplyTraceSync 按追溯号回写。
func ApplyTraceSync(db *gorm.DB, traceNo string, data *dto.PurchaseRecordSyncTraceUpdate) (*dto.PurchaseRecordSyncResultRead, *apperrors.AppError) {
	trace := strings.TrimSpace(traceNo)
	if trace == "" {
		return nil, apperrors.New("VALIDATION_ERROR", "追溯号不能为空", 422, nil)
	}
	var lines []models.PurchaseRequestLine
	if err := db.Where("trace_no = ?", trace).Order("id").Find(&lines).Error; err != nil {
		return nil, DatabaseError(err)
	}
	if len(lines) == 0 {
		return nil, apperrors.NotFound("该追溯号的申购记录")
	}
	requestIDs := map[int64]bool{}
	for _, l := range lines {
		requestIDs[l.PurchaseRequestID] = true
	}
	var reqs []models.PurchaseRequest
	if err := db.Where("id IN ?", keys(requestIDs)).Find(&reqs).Error; err != nil {
		return nil, DatabaseError(err)
	}
	affectedHeaders := 0
	for i := range reqs {
		req := &reqs[i]
		changed := false
		if data.ContractNo != nil && !isBlank(*data.ContractNo) && isBlank(deref(req.ContractNo)) {
			v := strings.TrimSpace(*data.ContractNo)
			req.ContractNo = &v
			changed = true
		}
		if data.VesselNo != nil && !isBlank(*data.VesselNo) && isBlank(deref(req.VesselNo)) {
			v := strings.TrimSpace(*data.VesselNo)
			req.VesselNo = &v
			changed = true
		}
		if data.ConsolidationPort != nil && !isBlank(*data.ConsolidationPort) && isBlank(deref(req.ConsolidationPort)) {
			v := strings.TrimSpace(*data.ConsolidationPort)
			req.ConsolidationPort = &v
			changed = true
		}
		if changed {
			req.Version++
			req.UpdatedAt = models.UTCNow()
			if err := db.Model(req).Select("*").Updates(req).Error; err != nil {
				return nil, DatabaseError(err)
			}
			affectedHeaders++
		}
	}
	affectedLines := 0
	for i := range lines {
		line := &lines[i]
		changed := false
		if data.Salesperson != nil && !isBlank(*data.Salesperson) && isBlank(deref(line.Salesperson)) {
			v := strings.TrimSpace(*data.Salesperson)
			line.Salesperson = &v
			changed = true
		}
		if data.Status != nil && !isBlank(*data.Status) {
			target := strings.TrimSpace(*data.Status)
			if line.Status != target && contains(statusProgression[target], line.Status) {
				line.Status = target
				changed = true
			}
		}
		if changed {
			line.Version++
			line.UpdatedAt = models.UTCNow()
			if err := db.Model(line).Select("Version", "UpdatedAt", "Salesperson", "Status").Updates(line).Error; err != nil {
				return nil, DatabaseError(err)
			}
			affectedLines++
		}
	}
	return &dto.PurchaseRecordSyncResultRead{
		AffectedHeaders: affectedHeaders, AffectedLines: affectedLines,
	}, nil
}

func isBlank(v string) bool { return v == "" || strings.TrimSpace(v) == "" }

func contains(list []string, v string) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

func keys(m map[int64]bool) []int64 {
	out := make([]int64, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

// UncodedMaterialRows 未编码计划导出行（物料编码申请模板）。
func UncodedMaterialRows(db *gorm.DB, keyword string) []map[string]any {
	var materials []models.PurchaseMaterial
	q := db.Where("material_code IS NULL AND status = ?", domain.PlanNormal)
	if keyword != "" {
		like := "%" + keyword + "%"
		q = q.Where("name LIKE ? OR model_spec LIKE ? OR material_code LIKE ? OR plan_no LIKE ?", like, like, like, like)
	}
	q.Order("id").Find(&materials)
	rows := make([]map[string]any, 0, len(materials))
	for i, item := range materials {
		rows = append(rows, map[string]any{
			"serial": i + 1, "name": item.Name, "model_spec": item.ModelSpec,
			"unit_name": item.UnitName, "warranty_managed": "否", "asset_category": "非资产",
			"application_reason": "当前无准确编码对应，需要新增编码", "department": "HXNI 检修维护部",
			"actual_demand_person": item.ActualDemandPerson,
		})
	}
	return rows
}

// PurchaseApplicationRows 采购申请/审批导出行。
func PurchaseApplicationRows(db *gorm.DB, materialIDs []int64, kind string) ([]map[string]any, *apperrors.AppError) {
	var materials []models.PurchaseMaterial
	q := db.Where("status = ?", domain.PlanNormal)
	if len(materialIDs) > 0 {
		q = q.Where("id IN ?", materialIDs)
	}
	q.Order("id").Find(&materials)
	if len(materialIDs) > 0 && len(materials) != len(dedupeIDs(materialIDs)) {
		return nil, apperrors.NotFound("申购计划")
	}
	missingLabels := map[string]bool{}
	for _, item := range materials {
		if deref2(item.MaterialCode) == "" {
			missingLabels["编码"] = true
		}
		if deref2(item.SubitemNo) == "" {
			missingLabels["子项号"] = true
		}
		if strings.TrimSpace(item.Usage) == "" {
			missingLabels["用途"] = true
		}
	}
	if len(missingLabels) > 0 && kind == "application" {
		return nil, apperrors.New("PURCHASE_APPLICATION_EXPORT_FIELDS_REQUIRED",
			"导出采购申请表前请补全："+joinSortedKeys(missingLabels), http.StatusConflict, nil)
	}
	rows := make([]map[string]any, 0, len(materials))
	today := time.Now().In(ShanghaiTZ)
	for i, item := range materials {
		if kind == "application" {
			rows = append(rows, map[string]any{
				"material_code": item.MaterialCode, "name": item.Name,
				"planned_qty":           serialize.DecimalToString(item.PlannedQty.Decimal),
				"purchase_responsible":  item.PurchaseResponsible,
				"demand_department":     item.DemandDepartment,
				"required_arrival_date": serialize.FormatDate(today.Add(90 * 24 * time.Hour)),
				"urgency":               item.Urgency, "usage": item.Usage, "remark": item.Remark,
				"subitem_no": item.SubitemNo,
			})
		} else {
			rows = append(rows, map[string]any{
				"serial": i + 1, "material_code": item.MaterialCode, "name": item.Name,
				"model_spec":  item.ModelSpec,
				"planned_qty": serialize.DecimalToString(item.PlannedQty.Decimal),
				"unit_name":   item.UnitName, "purchase_responsible": item.PurchaseResponsible,
				"department": "HXNI 检修维护部", "usage": item.Usage,
				"required_arrival_date": serialize.FormatDate(today.Add(80 * 24 * time.Hour)),
				"urgency":               item.Urgency, "remark": item.Remark, "subitem_no": item.SubitemNo,
			})
		}
	}
	return rows, nil
}

func deref2(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func joinSortedKeys(m map[string]bool) string {
	var keys []string
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return strings.Join(keys, "、")
}

// RunPeriodicCleanupWorker 周期清理（share 过期 + 归档计划清理 + 导出清理）。
func RunPeriodicCleanupWorker(db *gorm.DB, stop <-chan struct{}) {
	ticker := time.NewTicker(1 * time.Hour)
	defer ticker.Stop()
	for {
		select {
		case <-stop:
			return
		case <-ticker.C:
			CleanupExpiredShares(db)
		}
	}
}
