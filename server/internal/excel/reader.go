// Package excel 表格导入文件读取（等价 import_file_reader.py）：
// xlsx/xlsm 用 excelize 读缓存值；xls 用 extrame/xls；csv 自动探测编码。
package excel

import (
	"encoding/csv"
	"os"
	"strings"

	"github.com/extrame/xls"
	"github.com/xuri/excelize/v2"
	"golang.org/x/text/encoding/htmlindex"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
)

// ReadTabularRows 读取表格文件为二维原始值。
func ReadTabularRows(path string) ([][]any, *apperrors.AppError) {
	suffix := strings.ToLower(path[len(path)-5:])
	if strings.HasSuffix(suffix, ".xlsx") || strings.HasSuffix(suffix, ".xlsm") {
		return readXLSX(path)
	}
	if strings.HasSuffix(strings.ToLower(path), ".xls") {
		return readXLS(path)
	}
	if strings.HasSuffix(strings.ToLower(path), ".csv") {
		return readCSV(path)
	}
	return nil, apperrors.New("UNSUPPORTED_EXCEL_FILE", "仅支持 .xls、.xlsx 或 .csv 格式的表格文件", 0, nil)
}

func readXLSX(path string) ([][]any, *apperrors.AppError) {
	f, err := excelize.OpenFile(path, excelize.Options{})
	if err != nil {
		return nil, apperrors.New("INVALID_EXCEL_FILE", "无法读取 Excel 文件，请确认文件格式正确", 0, nil)
	}
	defer f.Close()
	sheet := f.GetSheetName(0)
	rows, err := f.GetRows(sheet, excelize.Options{RawCellValue: false})
	if err != nil {
		return nil, apperrors.New("INVALID_EXCEL_FILE", "无法读取 Excel 文件，请确认文件格式正确", 0, nil)
	}
	out := make([][]any, 0, len(rows))
	for _, row := range rows {
		cells := make([]any, len(row))
		for i, cell := range row {
			cells[i] = cell
		}
		out = append(out, cells)
	}
	return out, nil
}

func readXLS(path string) ([][]any, *apperrors.AppError) {
	book, err := xls.Open(path, "utf-8")
	if err != nil {
		return nil, apperrors.New("INVALID_EXCEL_FILE", "无法读取 Excel 文件，请确认文件格式正确", 0, nil)
	}
	sheet := book.GetSheet(0)
	if sheet == nil {
		return nil, apperrors.New("INVALID_EXCEL_FILE", "无法读取 Excel 文件，请确认文件格式正确", 0, nil)
	}
	var out [][]any
	for row := 0; row <= int(sheet.MaxRow); row++ {
		r := sheet.Row(row)
		if r == nil {
			out = append(out, []any{})
			continue
		}
		cols := r.LastCol()
		cells := make([]any, 0, cols)
		for col := 0; col < cols; col++ {
			cells = append(cells, r.Col(col))
		}
		out = append(out, cells)
	}
	return out, nil
}

func readCSV(path string) ([][]any, *apperrors.AppError) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, apperrors.New("INVALID_CSV_FILE", "无法读取 CSV 文件", 0, nil)
	}
	content, err := decodeCSV(raw)
	if err != nil {
		return nil, apperrors.New("INVALID_CSV_FILE", "无法解析 CSV 文件编码，请使用 UTF-8 或 GBK 编码", 0, nil)
	}
	reader := csv.NewReader(strings.NewReader(content))
	reader.FieldsPerRecord = -1
	records, err := reader.ReadAll()
	if err != nil {
		return nil, apperrors.New("INVALID_CSV_FILE", "无法解析 CSV 文件编码，请使用 UTF-8 或 GBK 编码", 0, nil)
	}
	out := make([][]any, 0, len(records))
	for _, rec := range records {
		cells := make([]any, len(rec))
		for i, v := range rec {
			cells[i] = v
		}
		out = append(out, cells)
	}
	return out, nil
}

func decodeCSV(raw []byte) (string, error) {
	// 尝试 UTF-8（含 BOM）
	text := strings.TrimPrefix(string(raw), "\ufeff")
	if strings.ToValidUTF8(string(raw), "") == string(raw) {
		return text, nil
	}
	// 回退 GB18030
	enc, err := htmlindex.Get("gb18030")
	if err != nil {
		return "", err
	}
	decoded, err := enc.NewDecoder().Bytes(raw)
	if err != nil {
		return "", err
	}
	return string(decoded), nil
}
