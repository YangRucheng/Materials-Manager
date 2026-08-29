package service

import (
	"fmt"
	"strconv"

	"gorm.io/gorm"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/excel"
	"github.com/yangrucheng/materials-manager/server/internal/models"
)

var materialCodeExpectedHeaders = []string{"编码", "名称", "型号", "记账单位名称"}

// MaterialCodeRow 解析后的物料编码行。
type MaterialCodeRow struct {
	MaterialCode string
	Name         *string
	ModelSpec    *string
	UnitName     string
}

func cellText(value any) string {
	if value == nil {
		return ""
	}
	switch v := value.(type) {
	case float64:
		if v == float64(int64(v)) {
			return strconv.FormatInt(int64(v), 10)
		}
		return strconv.FormatFloat(v, 'f', -1, 64)
	case float32:
		if v == float32(int32(v)) {
			return strconv.Itoa(int(v))
		}
		return strconv.FormatFloat(float64(v), 'f', -1, 32)
	}
	return trimSpace(fmt.Sprint(value))
}

func trimSpace(s string) string {
	start := 0
	end := len(s)
	for start < end && isSpace(rune(s[start])) {
		start++
	}
	for end > start && isSpace(rune(s[end-1])) {
		end--
	}
	return s[start:end]
}

func isSpace(r rune) bool {
	return r == ' ' || r == '\t' || r == '\n' || r == '\r' || r == '\u3000'
}

// ParseMaterialCodeFile 解析物料编码导入文件为行。
func ParseMaterialCodeFile(path string) ([]MaterialCodeRow, *apperrors.AppError) {
	rows, appErr := excel.ReadTabularRows(path)
	if appErr != nil {
		return nil, appErr
	}
	return parseMaterialCodes(rows)
}

func parseMaterialCodes(rows [][]any) ([]MaterialCodeRow, *apperrors.AppError) {
	headerRowIndex := -1
	headerIndexes := map[string]int{}
	limit := len(rows)
	if limit > 20 {
		limit = 20
	}
	for index := 0; index < limit; index++ {
		headers := make([]string, len(rows[index]))
		for i, cell := range rows[index] {
			headers[i] = cellText(cell)
		}
		indexes := map[string]int{}
		for i, header := range headers {
			if header != "" {
				indexes[header] = i
			}
		}
		allPresent := true
		for _, h := range materialCodeExpectedHeaders {
			if _, ok := indexes[h]; !ok {
				allPresent = false
				break
			}
		}
		if allPresent {
			headerRowIndex = index
			for _, h := range materialCodeExpectedHeaders {
				headerIndexes[h] = indexes[h]
			}
			break
		}
	}
	if headerRowIndex == -1 {
		return nil, apperrors.New("MATERIAL_CODE_IMPORT_HEADERS_MISSING",
			"表格缺少必需列：编码、名称、型号、记账单位名称", 0, nil)
	}
	var parsed []MaterialCodeRow
	seenCodes := map[string]int{}
	for index := headerRowIndex + 1; index < len(rows); index++ {
		rowNumber := index + 1
		row := rows[index]
		values := map[string]string{}
		for _, header := range materialCodeExpectedHeaders {
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
		materialCode := values["编码"]
		if materialCode == "" {
			return nil, apperrors.New("MATERIAL_CODE_IMPORT_CODE_REQUIRED",
				fmt.Sprintf("第 %d 行缺少编码", rowNumber), 0, map[string]any{"row": rowNumber})
		}
		if values["记账单位名称"] == "" {
			return nil, apperrors.New("MATERIAL_CODE_IMPORT_UNIT_REQUIRED",
				fmt.Sprintf("第 %d 行缺少记账单位名称", rowNumber), 0, map[string]any{"row": rowNumber})
		}
		if firstRow, ok := seenCodes[materialCode]; ok {
			return nil, apperrors.New("MATERIAL_CODE_IMPORT_DUPLICATE",
				fmt.Sprintf("编码“%s”在第 %d 行和第 %d 行重复", materialCode, firstRow, rowNumber),
				0, map[string]any{
					"material_code": materialCode,
					"first_row":     firstRow,
					"duplicate_row": rowNumber,
				})
		}
		if appErr := validateLength(materialCode, 64, rowNumber, "编码"); appErr != nil {
			return nil, appErr
		}
		if appErr := validateLength(values["名称"], 128, rowNumber, "名称"); appErr != nil {
			return nil, appErr
		}
		if appErr := validateLength(values["型号"], 255, rowNumber, "型号"); appErr != nil {
			return nil, appErr
		}
		if appErr := validateLength(values["记账单位名称"], 32, rowNumber, "记账单位名称"); appErr != nil {
			return nil, appErr
		}
		seenCodes[materialCode] = rowNumber
		name := nilOrValue(values["名称"])
		modelSpec := nilOrValue(values["型号"])
		parsed = append(parsed, MaterialCodeRow{
			MaterialCode: materialCode,
			Name:         name,
			ModelSpec:    modelSpec,
			UnitName:     values["记账单位名称"],
		})
	}
	if len(parsed) == 0 {
		return nil, apperrors.New("MATERIAL_CODE_IMPORT_EMPTY", "表格中没有可导入的物料编码数据", 0, nil)
	}
	return parsed, nil
}

func validateLength(value string, maximum, rowNumber int, header string) *apperrors.AppError {
	if len(value) > maximum {
		return apperrors.New("MATERIAL_CODE_IMPORT_VALUE_TOO_LONG",
			fmt.Sprintf("第 %d 行“%s”超过 %d 个字符", rowNumber, header, maximum), 0,
			map[string]any{"row": rowNumber, "column": header, "max_length": maximum})
	}
	return nil
}

func nilOrValue(s string) *string {
	if s == "" {
		return nil
	}
	v := s
	return &v
}

// ProcessMaterialCodeImport 解析 + 全量替换（单事务）。
func ProcessMaterialCodeImport(db *gorm.DB, filePath string) (map[string]any, *apperrors.AppError) {
	rows, appErr := ParseMaterialCodeFile(filePath)
	if appErr != nil {
		return nil, appErr
	}
	err := db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Where("1 = 1").Delete(&models.MaterialCodeLibrary{}).Error; err != nil {
			return err
		}
		for offset := 0; offset < len(rows); offset += 2000 {
			end := offset + 2000
			if end > len(rows) {
				end = len(rows)
			}
			batch := make([]models.MaterialCodeLibrary, 0, end-offset)
			for i := offset; i < end; i++ {
				r := rows[i]
				batch = append(batch, models.MaterialCodeLibrary{
					MaterialCode: r.MaterialCode,
					Name:         r.Name,
					ModelSpec:    r.ModelSpec,
					UnitName:     r.UnitName,
					CreatedAt:    models.UTCNow(),
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
	blankName := 0
	blankModel := 0
	for _, r := range rows {
		if r.Name == nil {
			blankName++
		}
		if r.ModelSpec == nil {
			blankModel++
		}
	}
	return map[string]any{
		"imported_count":       len(rows),
		"blank_name_count":     blankName,
		"blank_model_spec_count": blankModel,
	}, nil
}

// MaterialCodeExists 编码是否已收录（空串直接 false）。
func MaterialCodeExists(db *gorm.DB, materialCode string) bool {
	if materialCode == "" {
		return false
	}
	var count int64
	db.Model(&models.MaterialCodeLibrary{}).
		Where("material_code = ?", materialCode).Count(&count)
	return count > 0
}

// SearchMaterialCodes 编码库列表。
func SearchMaterialCodes(db *gorm.DB, keyword, name, modelSpec, materialCode string, page, pageSize int) ([]models.MaterialCodeLibrary, int, *apperrors.AppError) {
	q := db.Model(&models.MaterialCodeLibrary{})
	if clause, args := ContainsAnyClause(
		[]string{"material_code", "name", "model_spec"}, keyword); clause != "" {
		q = q.Where(clause, args...)
	}
	fieldFilters := []struct {
		column string
		value  string
	}{
		{"name", name}, {"model_spec", modelSpec}, {"material_code", materialCode},
	}
	for _, f := range fieldFilters {
		if clause, args := ContainsAnyClause([]string{f.column}, f.value); clause != "" {
			q = q.Where(clause, args...)
		}
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	var items []models.MaterialCodeLibrary
	if err := q.Order("material_code").Offset((page - 1) * pageSize).Limit(pageSize).Find(&items).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	return items, int(total), nil
}
