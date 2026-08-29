package service

import (
	"errors"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/shopspring/decimal"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"

	"github.com/yangrucheng/materials-manager/server/internal/database"
	"github.com/yangrucheng/materials-manager/server/internal/domain"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
)

// OperationLineInput 一条操作行（数量已解析）。
type OperationLineInput struct {
	StockMaterialID int64
	Quantity        decimal.Decimal
}

// OperationInput 库存业务入参（handler 已解析 occurred_at 为 UTC naive）。
type OperationInput struct {
	ClientRequestID string
	OccurredAt      time.Time
	SourceType      string
	BusinessReason  string
	ReceiverUnit    *string
	ReceiverName    *string
	SubitemNo       *string
	Lines           []OperationLineInput
}

// monthBefore 复刻 _months_before：按日历月回退 months 个月（日钳位到月末）。
func monthBefore(value time.Time, months int) time.Time {
	monthIndex := value.Year()*12 + int(value.Month()) - 1 - months
	year := monthIndex / 12
	zeroBased := monthIndex % 12
	month := zeroBased + 1
	day := value.Day()
	lastDay := daysInMonth(year, month)
	if day > lastDay {
		day = lastDay
	}
	return time.Date(year, time.Month(month), day, value.Hour(), value.Minute(), value.Second(), value.Nanosecond(), value.Location())
}

func daysInMonth(year, month int) int {
	return time.Date(year, time.Month(month)+1, 0, 0, 0, 0, 0, time.UTC).Day()
}

// RecentOutboundConsumption 近 6 个月出库消耗（排除冲销）。
func RecentOutboundConsumption(db *gorm.DB, materialIDs []int64, now time.Time) (map[int64]decimal.Decimal, error) {
	ids := dedupeIDs(materialIDs)
	if len(ids) == 0 {
		return map[int64]decimal.Decimal{}, nil
	}
	endAt := now
	startAt := monthBefore(endAt, 6)
	type row struct {
		StockMaterialID int64
		Qty             models.Decimal
	}
	var rows []row
	err := db.Raw(`
SELECT l.stock_material_id, SUM(l.quantity) AS qty
FROM stock_operation_line l
JOIN stock_operation op ON op.id = l.operation_id
LEFT JOIN stock_operation reversal ON reversal.reversal_of_id = op.id
WHERE l.stock_material_id IN ? 
  AND op.operation_type = 'OUTBOUND'
  AND op.source_type != 'REVERSAL'
  AND op.occurred_at >= ? AND op.occurred_at <= ?
  AND reversal.id IS NULL
GROUP BY l.stock_material_id`, ids, startAt, endAt).Scan(&rows).Error
	if err != nil {
		return nil, err
	}
	result := map[int64]decimal.Decimal{}
	for _, r := range rows {
		result[r.StockMaterialID] = r.Qty.Decimal
	}
	return result, nil
}

func dedupeIDs(ids []int64) []int64 {
	seen := map[int64]bool{}
	var out []int64
	for _, id := range ids {
		if !seen[id] {
			seen[id] = true
			out = append(out, id)
		}
	}
	return out
}

// GetOperation 查询流水。
func GetOperation(db *gorm.DB, operationID int64, forUpdate bool) (*models.StockOperation, *apperrors.AppError) {
	q := db.Preload("Lines")
	if forUpdate {
		q = q.Clauses(clause.Locking{Strength: "UPDATE"})
	}
	var item models.StockOperation
	err := q.First(&item, operationID).Error
	if IsNotFound(err) {
		return nil, apperrors.NotFound("库存流水")
	}
	if err != nil {
		return nil, DatabaseError(err)
	}
	return &item, nil
}

// EffectiveSourceType 读路径来源判定：mini_program_user_name_snapshot 非空 -> MINI_PROGRAM。
func EffectiveSourceType(item *models.StockOperation) string {
	if item.MiniProgramUserNameSnapshot != nil {
		return domain.SourceMiniProgram
	}
	return item.SourceType
}

func lockAndValidateMaterials(tx *gorm.DB, lines []OperationLineInput, additionalIDs []int64) (map[int64]*models.StockMaterial, *apperrors.AppError) {
	newIDs := map[int64]bool{}
	for _, line := range lines {
		newIDs[line.StockMaterialID] = true
	}
	idSet := map[int64]bool{}
	for id := range newIDs {
		idSet[id] = true
	}
	for _, id := range additionalIDs {
		idSet[id] = true
	}
	materialIDs := make([]int64, 0, len(idSet))
	for id := range idSet {
		materialIDs = append(materialIDs, id)
	}
	sort.Slice(materialIDs, func(i, j int) bool { return materialIDs[i] < materialIDs[j] })

	// 锁定余额
	var balances []models.StockBalance
	if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("stock_material_id IN ?", materialIDs).
		Order("stock_material_id").Find(&balances).Error; err != nil {
		return nil, DatabaseError(err)
	}
	if len(balances) != len(materialIDs) {
		return nil, apperrors.New("BALANCE_MISSING", "库存余额记录不存在", http.StatusConflict, nil)
	}
	// 锁定物资
	var materials []models.StockMaterial
	if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).
		Where("id IN ?", materialIDs).
		Order("id").Find(&materials).Error; err != nil {
		return nil, DatabaseError(err)
	}
	byID := map[int64]*models.StockMaterial{}
	for i := range materials {
		byID[materials[i].ID] = &materials[i]
	}
	var missing []int64
	for _, id := range materialIDs {
		if _, ok := byID[id]; !ok {
			missing = append(missing, id)
		}
	}
	if len(missing) > 0 {
		return nil, apperrors.New("NOT_FOUND", "二级库物资不存在", 0,
			map[string]any{"ids": missing})
	}
	for _, line := range lines {
		if appErr := ValidateQuantityPrecision(line.Quantity); appErr != nil {
			return nil, appErr
		}
	}
	return byID, nil
}

func validateOperationSemantics(operationType, sourceType string, receiverUnit, receiverName *string) *apperrors.AppError {
	if sourceType == domain.SourceInitialization && operationType != domain.OperationInbound {
		return apperrors.New("INVALID_SOURCE_TYPE", "初始化业务只能是入库", 0, nil)
	}
	if sourceType == domain.SourceMiniProgram && operationType != domain.OperationOutbound {
		return apperrors.New("INVALID_SOURCE_TYPE", "小程序来源只能是出库", 0, nil)
	}
	if operationType == domain.OperationInbound && receiverName != nil {
		return apperrors.New("INVALID_RECEIVER", "只有出库业务可以填写领用人", 0, nil)
	}
	if operationType == domain.OperationInbound && receiverUnit != nil {
		return apperrors.New("INVALID_RECEIVER_UNIT", "只有出库业务可以填写领用单位", 0, nil)
	}
	if operationType == domain.OperationOutbound && sourceType != domain.SourceReversal && (receiverName == nil || *receiverName == "") {
		return apperrors.New("RECEIVER_REQUIRED", "出库必须填写领用人", 0, nil)
	}
	return nil
}

// ReplayMaterials 重放指定物资的全部流水，重算 before/after 与余额。
func ReplayMaterials(tx *gorm.DB, materialIDs []int64) *apperrors.AppError {
	ids := dedupeIDs(materialIDs)
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	for _, materialID := range ids {
		var balance models.StockBalance
		err := tx.First(&balance, materialID).Error
		if IsNotFound(err) {
			return apperrors.New("BALANCE_MISSING", "库存余额记录不存在", http.StatusConflict, nil)
		}
		if err != nil {
			return DatabaseError(err)
		}
		type replayRow struct {
			ID            int64
			Quantity      models.Decimal
			OperationType string
		}
		var rows []replayRow
		err = tx.Raw(`
SELECT l.id, l.quantity, op.operation_type AS operation_type
FROM stock_operation_line l
JOIN stock_operation op ON op.id = l.operation_id
WHERE l.stock_material_id = ?
ORDER BY op.occurred_at, op.id, l.id`, materialID).Scan(&rows).Error
		if err != nil {
			return DatabaseError(err)
		}
		running := decimal.Zero
		for _, row := range rows {
			before := running
			if row.OperationType == domain.OperationInbound {
				running = running.Add(row.Quantity.Decimal)
			} else {
				running = running.Sub(row.Quantity.Decimal)
			}
			if err := tx.Model(&models.StockOperationLine{}).
				Where("id = ?", row.ID).
				Updates(map[string]any{"before_qty": before.String(), "after_qty": running.String()}).Error; err != nil {
				return DatabaseError(err)
			}
		}
		balance.Quantity = models.Decimal{Decimal: running}
		balance.Version++
		balance.UpdatedAt = models.UTCNow()
		if err := tx.Model(&models.StockBalance{}).
			Where("stock_material_id = ?", materialID).
			Updates(map[string]any{
				"quantity":   running.String(),
				"version":    gorm.Expr("version + 1"),
				"updated_at": balance.UpdatedAt,
			}).Error; err != nil {
			return DatabaseError(err)
		}
	}
	return nil
}

func findOperationByClientRequestID(tx *gorm.DB, clientRequestID string, forUpdate bool) *models.StockOperation {
	q := tx.Where("client_request_id = ?", clientRequestID)
	if forUpdate {
		q = q.Clauses(clause.Locking{Strength: "UPDATE"})
	}
	var item models.StockOperation
	if err := q.First(&item).Error; err != nil {
		return nil
	}
	_ = tx.Where("operation_id = ?", item.ID).Order("id").Find(&item.Lines).Error
	return &item
}

// CreateOperation 创建库存流水（入库/出库/冲销），含幂等与余额重放。
func CreateOperation(db *gorm.DB, data *OperationInput, operationType string,
	reversalOfID *int64, reversalOf *models.StockOperation,
	miniProgramUserName *string) (*models.StockOperation, *apperrors.AppError) {

	var result *models.StockOperation
	appErr := db.Transaction(func(tx *gorm.DB) error {
		if existing := findOperationByClientRequestID(tx, data.ClientRequestID, false); existing != nil {
			result = existing
			return nil
		}
		if data.SourceType == domain.SourceMiniProgram && miniProgramUserName == nil {
			return apperrors.New("INVALID_SOURCE_TYPE", "小程序来源只能由小程序出库创建", 0, nil)
		}
		if miniProgramUserName != nil && data.SourceType != domain.SourceMiniProgram {
			return apperrors.New("INVALID_SOURCE_TYPE", "小程序出库必须使用小程序来源", 0, nil)
		}
		if data.SourceType == domain.SourceReversal && reversalOfID == nil {
			return apperrors.New("INVALID_SOURCE_TYPE", "冲销来源只能由冲销接口创建", 0, nil)
		}
		if operationType == domain.OperationOutbound && data.BusinessReason == "" {
			return apperrors.New("BUSINESS_REASON_REQUIRED", "出库必须填写用途", 0, nil)
		}
		if appErr := validateOperationSemantics(operationType, data.SourceType, data.ReceiverUnit, data.ReceiverName); appErr != nil {
			return appErr
		}
		materials, appErr := lockAndValidateMaterials(tx, data.Lines, nil)
		if appErr != nil {
			return appErr
		}
		// 加锁后二次幂等校验
		if existing := findOperationByClientRequestID(tx, data.ClientRequestID, true); existing != nil {
			result = existing
			return nil
		}
		item := &models.StockOperation{
			OperationNo:                 "TMP-" + strings.ReplaceAll(security.UUID4Hex(), "-", "")[:20],
			OperationType:               operationType,
			OccurredAt:                  data.OccurredAt.UTC(),
			BusinessReason:              data.BusinessReason,
			ReceiverUnit:                data.ReceiverUnit,
			ReceiverName:                data.ReceiverName,
			SubitemNo:                   data.SubitemNo,
			SourceType:                  storedSourceType(data.SourceType),
			ReversalOfID:                reversalOfID,
			ClientRequestID:             data.ClientRequestID,
			MiniProgramUserNameSnapshot: miniProgramUserName,
		}
		if err := tx.Create(item).Error; err != nil {
			return err
		}
		prefix := "IN"
		if operationType == domain.OperationOutbound {
			prefix = "OUT"
		}
		item.OperationNo = fmt.Sprintf("%s%s%06d", prefix, item.OccurredAt.Format("20060102"), item.ID)
		if err := tx.Model(&models.StockOperation{}).Where("id = ?", item.ID).
			Update("operation_no", item.OperationNo).Error; err != nil {
			return err
		}

		originalLines := map[int64]models.StockOperationLine{}
		if reversalOf != nil {
			for _, l := range reversalOf.Lines {
				originalLines[l.StockMaterialID] = l
			}
		}
		reversalQuantities := map[int64]decimal.Decimal{}
		for _, line := range data.Lines {
			if reversalOf == nil {
				reversalQuantities[line.StockMaterialID] = line.Quantity
				continue
			}
			originalLine, ok := originalLines[line.StockMaterialID]
			if !ok {
				return apperrors.New("INVALID_REVERSAL_LINE", "冲销行不在原流水内", 0, nil)
			}
			if line.Quantity.GreaterThan(originalLine.RemainingQty.Decimal) {
				return apperrors.New("INSUFFICIENT_QUANTITY",
					fmt.Sprintf("冲销数量超过剩余可冲数量 %s", serializeDecimal(originalLine.RemainingQty.Decimal)),
					http.StatusConflict, nil)
			}
			reversalQuantities[line.StockMaterialID] = line.Quantity
		}

		lines := make([]models.StockOperationLine, 0, len(data.Lines))
		for _, line := range data.Lines {
			material := materials[line.StockMaterialID]
			lines = append(lines, models.StockOperationLine{
				OperationID:          item.ID,
				StockMaterialID:      line.StockMaterialID,
				Quantity:             models.Decimal{Decimal: reversalQuantities[line.StockMaterialID]},
				RemainingQty:         models.Decimal{Decimal: reversalQuantities[line.StockMaterialID]},
				BeforeQty:            models.Decimal{Decimal: decimal.Zero},
				AfterQty:             models.Decimal{Decimal: decimal.Zero},
				MaterialNameSnapshot: material.Name,
				ModelSpecSnapshot:    material.ModelSpec,
				UnitNameSnapshot:     material.UnitName,
			})
		}
		if err := tx.Create(&lines).Error; err != nil {
			return err
		}
		item.Lines = lines
		// 冲销扣减原行可冲余量
		if reversalOf != nil {
			for _, line := range data.Lines {
				origID := originalLines[line.StockMaterialID].ID
				newRemaining := originalLines[line.StockMaterialID].RemainingQty.Decimal.Sub(reversalQuantities[line.StockMaterialID])
				if err := tx.Model(&models.StockOperationLine{}).Where("id = ?", origID).
					Update("remaining_qty", newRemaining.String()).Error; err != nil {
					return err
				}
			}
		}
		materialIDs := make([]int64, 0, len(materials))
		for id := range materials {
			materialIDs = append(materialIDs, id)
		}
		if appErr := ReplayMaterials(tx, materialIDs); appErr != nil {
			return appErr
		}
		// 审计
		action := "CREATED"
		if reversalOfID != nil {
			action = "REVERSED"
		}
		if appErr := LogOperationEvent(tx, item, action, nil); appErr != nil {
			return appErr
		}
		// Webhook（P8 实现投递；此处仅登记）
		if reversalOfID == nil {
			eventType := domain.WebhookStockInboundCreated
			if operationType == domain.OperationOutbound {
				eventType = domain.WebhookStockOutboundCreated
			}
			EnqueueWebhookEvent(tx, eventType, buildStockOperationPayload(item))
		}
		result = item
		return nil
	})
	if appErr != nil {
		return nil, mapTxError(appErr)
	}
	return result, nil
}

func storedSourceType(sourceType string) string {
	if sourceType == domain.SourceMiniProgram {
		return domain.SourceManual
	}
	return sourceType
}

func buildStockOperationPayload(item *models.StockOperation) map[string]any {
	lines := make([]map[string]any, 0, len(item.Lines))
	for _, line := range item.Lines {
		lines = append(lines, map[string]any{
			"name":       line.MaterialNameSnapshot,
			"model_spec": line.ModelSpecSnapshot,
			"quantity":   serializeDecimal(line.Quantity.Decimal),
			"unit_name":  line.UnitNameSnapshot,
			"before_qty": serializeDecimal(line.BeforeQty.Decimal),
			"after_qty":  serializeDecimal(line.AfterQty.Decimal),
		})
	}
	return map[string]any{
		"occurred_at":     item.OccurredAt.UTC().Format("2006-01-02T15:04:05Z"),
		"source_type":     EffectiveSourceType(item),
		"business_reason": item.BusinessReason,
		"receiver_unit":   item.ReceiverUnit,
		"receiver_name":   item.ReceiverName,
		"subitem_no":      item.SubitemNo,
		"materials":       lines,
	}
}

func mapTxError(err error) *apperrors.AppError {
	var appErr *apperrors.AppError
	if errors.As(err, &appErr) {
		return appErr
	}
	if database.IsDuplicateError(err) {
		return apperrors.New("DATA_CONFLICT", "数据约束冲突", http.StatusConflict, nil)
	}
	return DatabaseError(err)
}

// SearchOperations 流水列表筛选。
func SearchOperations(db *gorm.DB, operationNo, operationType, materialName, sourceType string, startAt, endAt *time.Time, page, pageSize int) ([]models.StockOperation, int, *apperrors.AppError) {
	// 每个查询独立 Statement：Count 的 Distinct("stock_operation.id") 不能污染 Find 的 Selects（MySQL 3065）。
	build := func() *gorm.DB {
		q2 := db.Session(&gorm.Session{NewDB: true}).Model(&models.StockOperation{})
		if operationNo != "" {
			q2 = q2.Where("operation_no LIKE ?", "%"+operationNo+"%")
		}
		if operationType != "" {
			q2 = q2.Where("operation_type = ?", operationType)
		}
		if materialName != "" {
			if clause, args := ContainsAnyClause(
				[]string{"l.material_name_snapshot", "l.model_spec_snapshot"}, materialName); clause != "" {
				q2 = q2.Joins("JOIN stock_operation_line l ON l.operation_id = stock_operation.id").
					Where(clause, args...)
			}
		}
		if sourceType == domain.SourceMiniProgram {
			q2 = q2.Where("mini_program_user_name_snapshot IS NOT NULL")
		} else if sourceType == domain.SourceManual {
			q2 = q2.Where("source_type = ? AND mini_program_user_name_snapshot IS NULL", domain.SourceManual)
		} else if sourceType != "" {
			q2 = q2.Where("source_type = ?", sourceType)
		}
		if startAt != nil {
			q2 = q2.Where("occurred_at >= ?", *startAt)
		}
		if endAt != nil {
			q2 = q2.Where("occurred_at <= ?", *endAt)
		}
		return q2
	}
	var total int64
	// 计数：只 DISTINCT id
	if err := build().Distinct("stock_operation.id").Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	var items []models.StockOperation
	// 列表：DISTINCT 全列（JOIN 去重且 ORDER BY 列在选择集中，兼容 MySQL 3065）
	if err := build().Distinct().Preload("Lines").
		Order("occurred_at DESC, id DESC").
		Offset((page - 1) * pageSize).Limit(pageSize).Find(&items).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	return items, int(total), nil
}

// InventoryBalanceItem 库存余额行（含补库建议）。
type InventoryBalanceItem struct {
	StockMaterialID      int64
	Name                 string
	Alias                *string
	ModelSpec            string
	UnitName             string
	CurrentQty           decimal.Decimal
	MinimumQty           *decimal.Decimal
	IsLowStock           bool
	SuggestedPurchaseQty decimal.Decimal
	UpdatedAt            time.Time
}

// InventoryBalances 库存余额分页查询。
func InventoryBalances(db *gorm.DB, keyword string, minimumQty, maximumQty *decimal.Decimal, lowStockOnly bool, page, pageSize int, materialID *int64) ([]InventoryBalanceItem, int, *apperrors.AppError) {
	// 每个查询独立 Statement，避免 Count/Find 相互污染（MySQL 3065）。
	build := func() *gorm.DB {
		q2 := db.Session(&gorm.Session{NewDB: true}).Model(&models.StockMaterial{}).
			Joins("JOIN stock_balance ON stock_balance.stock_material_id = stock_material.id").
			Joins("LEFT JOIN stock_replenishment_policy ON stock_replenishment_policy.stock_material_id = stock_material.id")
		if materialID != nil {
			q2 = q2.Where("stock_material.id = ?", *materialID)
		}
		if clause, args := ContainsAnyClause(
			[]string{"stock_material.name", "stock_material.alias", "stock_material.model_spec"}, keyword); clause != "" {
			q2 = q2.Where(clause, args...)
		}
		if minimumQty != nil {
			q2 = q2.Where("stock_balance.quantity >= ?", minimumQty.String())
		}
		if maximumQty != nil {
			q2 = q2.Where("stock_balance.quantity <= ?", maximumQty.String())
		}
		if lowStockOnly {
			q2 = q2.Where("stock_replenishment_policy.enabled = ?", true).
				Where("stock_balance.quantity <= stock_replenishment_policy.minimum_qty")
		}
		return q2.Distinct("stock_material.id")
	}
	var total int64
	if err := build().Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	type balanceRow struct {
		StockMaterialID int64
		Name            string
		Alias           *string
		ModelSpec       string
		UnitName        string
		Quantity        models.Decimal
		MinimumQty      *models.Decimal
		PolicyEnabled   bool
		BalanceUpdated  time.Time
	}
	var rows []balanceRow
	err := build().Select(`stock_material.id AS stock_material_id, stock_material.name, stock_material.alias,
		stock_material.model_spec, stock_material.unit_name,
		stock_balance.quantity, stock_replenishment_policy.minimum_qty,
		COALESCE(stock_replenishment_policy.enabled, 0) AS policy_enabled,
		stock_balance.updated_at AS balance_updated`).
		Order("stock_material.id").
		Offset((page - 1) * pageSize).Limit(pageSize).Scan(&rows).Error
	if err != nil {
		return nil, 0, DatabaseError(err)
	}
	ids := make([]int64, 0, len(rows))
	for _, r := range rows {
		ids = append(ids, r.StockMaterialID)
	}
	consumption := map[int64]decimal.Decimal{}
	if len(ids) > 0 {
		c, err := RecentOutboundConsumption(db, ids, time.Now().UTC())
		if err != nil {
			return nil, 0, DatabaseError(err)
		}
		consumption = c
	}
	items := make([]InventoryBalanceItem, 0, len(rows))
	for _, r := range rows {
		current := r.Quantity.Decimal
		low := r.PolicyEnabled && current.LessThanOrEqual(r.MinimumQty.Decimal)
		var minPtr *decimal.Decimal
		if r.PolicyEnabled {
			min := r.MinimumQty.Decimal
			minPtr = &min
		}
		items = append(items, InventoryBalanceItem{
			StockMaterialID:      r.StockMaterialID,
			Name:                 r.Name,
			Alias:                r.Alias,
			ModelSpec:            r.ModelSpec,
			UnitName:             r.UnitName,
			CurrentQty:           current,
			MinimumQty:           minPtr,
			IsLowStock:           low,
			SuggestedPurchaseQty: consumption[r.StockMaterialID],
			UpdatedAt:            r.BalanceUpdated,
		})
	}
	return items, int(total), nil
}

// UpdateOperation 更新流水（乐观锁 + 语义校验 + 重放）。
func UpdateOperation(db *gorm.DB, item *models.StockOperation, data *OperationInput, version int, operationType string) (*models.StockOperation, *apperrors.AppError) {
	if appErr := ValidateVersion(version, item.Version); appErr != nil {
		return nil, appErr
	}
	if item.MiniProgramUserNameSnapshot != nil && data.SourceType != domain.SourceMiniProgram {
		return nil, apperrors.New("INVALID_SOURCE_TYPE", "小程序流水必须保留小程序来源", 0, nil)
	}
	if item.MiniProgramUserNameSnapshot == nil && data.SourceType == domain.SourceMiniProgram {
		return nil, apperrors.New("INVALID_SOURCE_TYPE", "普通流水不能改为小程序来源", 0, nil)
	}
	if operationType == domain.OperationOutbound && data.BusinessReason == "" {
		return nil, apperrors.New("BUSINESS_REASON_REQUIRED", "出库必须填写用途", 0, nil)
	}
	if appErr := validateOperationSemantics(operationType, data.SourceType, data.ReceiverUnit, data.ReceiverName); appErr != nil {
		return nil, appErr
	}
	before := operationSnapshot(item)
	oldMaterialIDs := map[int64]bool{}
	for _, line := range item.Lines {
		oldMaterialIDs[line.StockMaterialID] = true
	}
	var additional []int64
	for id := range oldMaterialIDs {
		additional = append(additional, id)
	}

	var result *models.StockOperation
	appErr := db.Transaction(func(tx *gorm.DB) error {
		materials, appErr := lockAndValidateMaterials(tx, data.Lines, additional)
		if appErr != nil {
			return appErr
		}
		item.OperationType = operationType
		item.OccurredAt = data.OccurredAt.UTC()
		item.SourceType = storedSourceType(data.SourceType)
		item.BusinessReason = data.BusinessReason
		item.ReceiverUnit = data.ReceiverUnit
		item.ReceiverName = data.ReceiverName
		item.SubitemNo = data.SubitemNo
		item.Version++
		item.UpdatedAt = models.UTCNow()
		// 载入现有行（重建关联）
		var existingLines []models.StockOperationLine
		if err := tx.Where("operation_id = ?", item.ID).Find(&existingLines).Error; err != nil {
			return err
		}
		existingByMaterial := map[int64]*models.StockOperationLine{}
		for i := range existingLines {
			existingByMaterial[existingLines[i].StockMaterialID] = &existingLines[i]
		}
		var updated []models.StockOperationLine
		for _, line := range data.Lines {
			material := materials[line.StockMaterialID]
			stored := existingByMaterial[line.StockMaterialID]
			if stored == nil {
				// 新建行
				newLine := models.StockOperationLine{
					OperationID:          item.ID,
					StockMaterialID:      line.StockMaterialID,
					Quantity:             models.Decimal{Decimal: line.Quantity},
					RemainingQty:         models.Decimal{Decimal: line.Quantity},
					BeforeQty:            models.Decimal{Decimal: decimal.Zero},
					AfterQty:             models.Decimal{Decimal: decimal.Zero},
					MaterialNameSnapshot: material.Name,
					ModelSpecSnapshot:    material.ModelSpec,
					UnitNameSnapshot:     material.UnitName,
				}
				if err := tx.Create(&newLine).Error; err != nil {
					return err
				}
				updated = append(updated, newLine)
			} else {
				remaining := stored.RemainingQty.Decimal
				if line.Quantity.LessThan(remaining) {
					remaining = line.Quantity
				}
				*stored = models.StockOperationLine{
					ID:                   stored.ID,
					OperationID:          item.ID,
					StockMaterialID:      line.StockMaterialID,
					Quantity:             models.Decimal{Decimal: line.Quantity},
					RemainingQty:         models.Decimal{Decimal: remaining},
					BeforeQty:            stored.BeforeQty,
					AfterQty:             stored.AfterQty,
					MaterialNameSnapshot: material.Name,
					ModelSpecSnapshot:    material.ModelSpec,
					UnitNameSnapshot:     material.UnitName,
					Audit:                stored.Audit,
				}
				if err := tx.Model(&models.StockOperationLine{}).Where("id = ?", stored.ID).
					Updates(map[string]any{
						"quantity":               line.Quantity.String(),
						"remaining_qty":          remaining.String(),
						"material_name_snapshot": material.Name,
						"model_spec_snapshot":    material.ModelSpec,
						"unit_name_snapshot":     material.UnitName,
					}).Error; err != nil {
					return err
				}
				updated = append(updated, *stored)
			}
		}
		item.Lines = updated
		if err := tx.Model(&models.StockOperation{}).Where("id = ?", item.ID).
			Updates(map[string]any{
				"operation_type":  operationType,
				"occurred_at":     item.OccurredAt,
				"source_type":     item.SourceType,
				"business_reason": item.BusinessReason,
				"receiver_unit":   item.ReceiverUnit,
				"receiver_name":   item.ReceiverName,
				"subitem_no":      item.SubitemNo,
				"version":         gorm.Expr("version + 1"),
				"updated_at":      item.UpdatedAt,
			}).Error; err != nil {
			return err
		}
		// 删除被移除的行
		kept := map[int64]bool{}
		for _, line := range updated {
			kept[line.ID] = true
		}
		var removableIDs []int64
		for _, line := range existingLines {
			if !kept[line.ID] {
				removableIDs = append(removableIDs, line.ID)
			}
		}
		if len(removableIDs) > 0 {
			if err := tx.Delete(&models.StockOperationLine{}, removableIDs).Error; err != nil {
				return err
			}
		}
		allIDs := map[int64]bool{}
		for id := range oldMaterialIDs {
			allIDs[id] = true
		}
		for _, line := range data.Lines {
			allIDs[line.StockMaterialID] = true
		}
		replayIDs := make([]int64, 0, len(allIDs))
		for id := range allIDs {
			replayIDs = append(replayIDs, id)
		}
		if appErr := ReplayMaterials(tx, replayIDs); appErr != nil {
			return appErr
		}
		if appErr := LogOperationEvent(tx, item, "UPDATED", before); appErr != nil {
			return appErr
		}
		result = item
		return nil
	})
	if appErr != nil {
		return nil, mapTxError(appErr)
	}
	return result, nil
}

// ReverseOperation 冲销流水。
func ReverseOperation(db *gorm.DB, original *models.StockOperation, data *OperationInput) (*models.StockOperation, *apperrors.AppError) {
	if existing := findOperationByClientRequestID(db, data.ClientRequestID, false); existing != nil {
		return existing, nil
	}
	now := time.Now().UTC()
	reverseAt := now
	origPlus := original.OccurredAt.UTC().Add(time.Microsecond)
	if origPlus.After(now) {
		reverseAt = origPlus
	}
	reverseType := domain.OperationInbound
	if original.OperationType == domain.OperationInbound {
		reverseType = domain.OperationOutbound
	}
	reversalID := original.ID
	payload := &OperationInput{
		ClientRequestID: data.ClientRequestID,
		OccurredAt:      reverseAt,
		SourceType:      domain.SourceReversal,
		BusinessReason:  data.BusinessReason,
		ReceiverUnit:    nil,
		ReceiverName:    nil,
		SubitemNo:       original.SubitemNo,
		Lines:           data.Lines,
	}
	return CreateOperation(db, payload, reverseType, &reversalID, original, nil)
}

func operationSnapshot(item *models.StockOperation) map[string]any {
	lines := make([]map[string]any, 0, len(item.Lines))
	for _, line := range item.Lines {
		lines = append(lines, map[string]any{
			"stock_material_id": line.StockMaterialID,
			"quantity":          serializeDecimal(line.Quantity.Decimal),
		})
	}
	return map[string]any{
		"operation_type":         item.OperationType,
		"occurred_at":            item.OccurredAt.UTC().Format("2006-01-02T15:04:05.000000Z"),
		"source_type":            EffectiveSourceType(item),
		"business_reason":        item.BusinessReason,
		"receiver_unit":          item.ReceiverUnit,
		"receiver_name":          item.ReceiverName,
		"subitem_no":             item.SubitemNo,
		"mini_program_user_name": item.MiniProgramUserNameSnapshot,
		"lines":                  lines,
	}
}

func serializeDecimal(d decimal.Decimal) string {
	return serialize.DecimalToString(d)
}
