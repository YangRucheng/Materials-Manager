package service

import (
	"fmt"
	"strings"
	"time"

	"github.com/shopspring/decimal"
	"gorm.io/gorm"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/excel"
	"github.com/yangrucheng/materials-manager/server/internal/models"
)

var huaxingExpectedHeaders = []string{
	"首次入库日期", "仓库", "货品编码", "货品名称", "型号", "数量", "单位", "申购人", "申购部门", "子项号名称",
}

var huaxingHeaderAliases = map[string]string{"首次入库时间": "首次入库日期"}

// HuaXingRow 解析后的华星库存行。
type HuaXingRow struct {
	FirstInboundDate   *time.Time
	Warehouse          *string
	MaterialCode       string
	Name               *string
	ModelSpec          *string
	Quantity           *decimal.Decimal
	UnitName           *string
	Purchaser          *string
	PurchaseDepartment *string
	SubitemNoName      *string
}

// ParseHuaXingFile 解析华星库存导入文件。
func ParseHuaXingFile(path string) ([]HuaXingRow, *apperrors.AppError) {
	rows, appErr := excel.ReadTabularRows(path)
	if appErr != nil {
		return nil, appErr
	}
	return parseHuaXing(rows)
}

func parseHuaXing(rows [][]any) ([]HuaXingRow, *apperrors.AppError) {
	headerRowIndex := -1
	headerIndexes := map[string]int{}
	limit := len(rows)
	if limit > 20 {
		limit = 20
	}
	for index := 0; index < limit; index++ {
		rawHeaders := make([]string, len(rows[index]))
		for i, cell := range rows[index] {
			rawHeaders[i] = cellText(cell)
		}
		headers := make([]string, len(rawHeaders))
		for i, h := range rawHeaders {
			if alias, ok := huaxingHeaderAliases[h]; ok {
				headers[i] = alias
			} else {
				headers[i] = h
			}
		}
		indexes := map[string]int{}
		for i, h := range headers {
			if h != "" {
				indexes[h] = i
			}
		}
		allPresent := true
		for _, h := range huaxingExpectedHeaders {
			if _, ok := indexes[h]; !ok {
				allPresent = false
				break
			}
		}
		if allPresent {
			headerRowIndex = index
			for _, h := range huaxingExpectedHeaders {
				headerIndexes[h] = indexes[h]
			}
			break
		}
	}
	if headerRowIndex == -1 {
		return nil, apperrors.New("HUAXING_IMPORT_HEADERS_MISSING",
			"表格缺少必需列：首次入库日期、仓库、货品编码、货品名称、型号、数量、单位、申购人、申购部门、子项号名称", 0, nil)
	}
	dateIndex := headerIndexes["首次入库日期"]
	quantityIndex := headerIndexes["数量"]
	var parsed []HuaXingRow
	for index := headerRowIndex + 1; index < len(rows); index++ {
		rowNumber := index + 1
		row := rows[index]
		values := map[string]string{}
		for _, header := range huaxingExpectedHeaders {
			col := headerIndexes[header]
			if col < len(row) {
				values[header] = cellText(row[col])
			} else {
				values[header] = ""
			}
		}
		anyValue := false
		for _, v := range values {
			if v != "" {
				anyValue = true
				break
			}
		}
		if !anyValue {
			continue
		}
		materialCode := values["货品编码"]
		if materialCode == "" {
			return nil, apperrors.New("HUAXING_IMPORT_CODE_REQUIRED",
				fmt.Sprintf("第 %d 行缺少货品编码", rowNumber), 0, map[string]any{"row": rowNumber})
		}
		lengthChecks := []struct {
			header string
			max    int
		}{
			{"货品编码", 64}, {"仓库", 128}, {"货品名称", 255}, {"型号", 255},
			{"单位", 32}, {"申购人", 128}, {"申购部门", 128}, {"子项号名称", 255},
		}
		for _, lc := range lengthChecks {
			if appErr := huaxingLength(values[lc.header], lc.max, rowNumber, lc.header); appErr != nil {
				return nil, appErr
			}
		}
		var dateVal *time.Time
		if dateIndex < len(row) {
			dateVal = cellDate(row[dateIndex])
		}
		var qty *decimal.Decimal
		if quantityIndex < len(row) {
			q, appErr := cellQuantity(row[quantityIndex], rowNumber)
			if appErr != nil {
				return nil, appErr
			}
			qty = q
		}
		parsed = append(parsed, HuaXingRow{
			FirstInboundDate:   dateVal,
			Warehouse:          nilOrValue(values["仓库"]),
			MaterialCode:       materialCode,
			Name:               nilOrValue(values["货品名称"]),
			ModelSpec:          nilOrValue(values["型号"]),
			Quantity:           qty,
			UnitName:           nilOrValue(values["单位"]),
			Purchaser:          nilOrValue(values["申购人"]),
			PurchaseDepartment: nilOrValue(values["申购部门"]),
			SubitemNoName:      nilOrValue(values["子项号名称"]),
		})
	}
	if len(parsed) == 0 {
		return nil, apperrors.New("HUAXING_IMPORT_EMPTY", "表格中没有可导入的华星库存数据", 0, nil)
	}
	return parsed, nil
}

func huaxingLength(value string, maximum, rowNumber int, header string) *apperrors.AppError {
	if len(value) > maximum {
		return apperrors.New("HUAXING_IMPORT_VALUE_TOO_LONG",
			fmt.Sprintf("第 %d 行“%s”超过 %d 个字符", rowNumber, header, maximum), 0,
			map[string]any{"row": rowNumber, "column": header, "max_length": maximum})
	}
	return nil
}

func cellDate(value any) *time.Time {
	if value == nil {
		return nil
	}
	switch v := value.(type) {
	case time.Time:
		d := v
		return &d
	}
	text := strings.TrimSpace(fmt.Sprint(value))
	if text == "" {
		return nil
	}
	// 尝试 ISO 前缀 10 位（YYYY-MM-DD）
	if len(text) >= 10 {
		if t, err := time.Parse("2006-01-02", text[:10]); err == nil {
			return &t
		}
	}
	if t, err := time.Parse("2006/01/02", text); err == nil {
		return &t
	}
	return nil
}

func cellQuantity(value any, rowNumber int) (*decimal.Decimal, *apperrors.AppError) {
	if value == nil {
		return nil, nil
	}
	text := strings.TrimSpace(fmt.Sprint(value))
	if text == "" {
		return nil, nil
	}
	dec, err := decimal.NewFromString(text)
	if err != nil {
		return nil, apperrors.New("HUAXING_IMPORT_INVALID_QUANTITY",
			fmt.Sprintf("第 %d 行数量不是有效数值", rowNumber), 0, map[string]any{"row": rowNumber})
	}
	return &dec, nil
}

// ProcessHuaXingImport 解析 + 全字段去重 + 全量替换。
func ProcessHuaXingImport(db *gorm.DB, filePath string) (map[string]any, *apperrors.AppError) {
	rows, appErr := ParseHuaXingFile(filePath)
	if appErr != nil {
		return nil, appErr
	}
	seen := map[string]bool{}
	var deduped []HuaXingRow
	for _, row := range rows {
		key := huaxingDedupeKey(&row)
		if seen[key] {
			continue
		}
		seen[key] = true
		deduped = append(deduped, row)
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Where("1 = 1").Delete(&models.HuaXingInventory{}).Error; err != nil {
			return err
		}
		for offset := 0; offset < len(deduped); offset += 2000 {
			end := offset + 2000
			if end > len(deduped) {
				end = len(deduped)
			}
			batch := make([]models.HuaXingInventory, 0, end-offset)
			for i := offset; i < end; i++ {
				r := deduped[i]
				var qty *models.Decimal
				if r.Quantity != nil {
					d := models.Decimal{Decimal: *r.Quantity}
					qty = &d
				}
				batch = append(batch, models.HuaXingInventory{
					FirstInboundDate:   r.FirstInboundDate,
					Warehouse:          r.Warehouse,
					MaterialCode:       nilOrValue(r.MaterialCode),
					Name:               r.Name,
					ModelSpec:          r.ModelSpec,
					Quantity:           qty,
					UnitName:           r.UnitName,
					Purchaser:          r.Purchaser,
					PurchaseDepartment: r.PurchaseDepartment,
					SubitemNoName:      r.SubitemNoName,
					CreatedAt:          models.UTCNow(),
				})
			}
			if err := tx.Create(&batch).Error; err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return nil, DatabaseError(err)
	}
	return map[string]any{
		"imported_count":     len(deduped),
		"deduplicated_count": len(rows) - len(deduped),
	}, nil
}

func huaxingDedupeKey(row *HuaXingRow) string {
	parts := []string{
		fmt.Sprint(row.FirstInboundDate),
		strVal(row.Warehouse), row.MaterialCode, strVal(row.Name), strVal(row.ModelSpec),
		fmt.Sprint(row.Quantity), strVal(row.UnitName), strVal(row.Purchaser),
		strVal(row.PurchaseDepartment), strVal(row.SubitemNoName),
	}
	return strings.Join(parts, "\x00")
}

func strVal(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// HuaXingFilterOptions 申购部门/申购人去空 distinct。
func HuaXingFilterOptions(db *gorm.DB) ([]string, []string, *apperrors.AppError) {
	var departments, purchasers []string
	if err := db.Model(&models.HuaXingInventory{}).
		Where("purchase_department IS NOT NULL AND TRIM(purchase_department) != ''").
		Distinct().Order("purchase_department").Pluck("purchase_department", &departments).Error; err != nil {
		return nil, nil, DatabaseError(err)
	}
	if err := db.Model(&models.HuaXingInventory{}).
		Where("purchaser IS NOT NULL AND TRIM(purchaser) != ''").
		Distinct().Order("purchaser").Pluck("purchaser", &purchasers).Error; err != nil {
		return nil, nil, DatabaseError(err)
	}
	return departments, purchasers, nil
}

// SearchHuaXingInventory 列表（字段独立 OR + 下拉多选 IN + 兼容 keyword）。
func SearchHuaXingInventory(db *gorm.DB, keyword, materialCode, name, modelSpec, purchaseDepartment, purchaser string, page, pageSize int) ([]models.HuaXingInventory, int, *apperrors.AppError) {
	q := db.Model(&models.HuaXingInventory{})
	for _, f := range []struct {
		column string
		value  string
	}{{"material_code", materialCode}, {"name", name}, {"model_spec", modelSpec}} {
		if clause, args := ContainsAnyClause([]string{f.column}, f.value); clause != "" {
			q = q.Where(clause, args...)
		}
	}
	for _, f := range []struct {
		column string
		value  string
	}{{"purchase_department", purchaseDepartment}, {"purchaser", purchaser}} {
		if terms := SplitOrSearchTerms(f.value); len(terms) > 0 {
			q = q.Where(f.column+" IN ?", terms)
		}
	}
	if clause, args := ContainsAnyClause(
		[]string{"material_code", "name", "model_spec", "purchaser"}, keyword); clause != "" {
		q = q.Where(clause, args...)
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	var items []models.HuaXingInventory
	if err := q.Order("id").Offset((page - 1) * pageSize).Limit(pageSize).Find(&items).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	return items, int(total), nil
}
