// Package excel 导出渲染（模板渲染 + 结果导出），等价 excel_export_service.py。
package excel

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/xuri/excelize/v2"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
)

const xlsxContentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

var illegalExcelChars = regexp.MustCompile(`[\x00-\x08\x0B\x0C\x0E-\x1F]`)

// ExcelSpec 模板 JSON 结构。
type ExcelSpec struct {
	OutputFilename  string               `json:"output_filename"`
	Sheet           SheetSpec            `json:"sheet"`
	Styles          map[string]StyleSpec `json:"styles"`
	Columns         []ColumnSpec         `json:"columns"`
	ValidationLists map[string][]string  `json:"validation_lists"`
}

type SheetSpec struct {
	Title                       string             `json:"title"`
	HeaderRow                   int                `json:"header_row"`
	DataStartRow                int                `json:"data_start_row"`
	FreezePanes                 string             `json:"freeze_panes"`
	ColumnWidths                map[string]float64 `json:"column_widths"`
	RowHeights                  map[string]float64 `json:"row_heights"`
	MergedCells                 []string           `json:"merged_cells"`
	TitleCell                   string             `json:"title_cell"`
	RequiredRow                 int                `json:"required_row"`
	InstructionRow              int                `json:"instruction_row"`
	MinimumDataRows             int                `json:"minimum_data_rows"`
	ShowGridLines               *bool              `json:"show_grid_lines"`
	HighlightMissingFirstColumn bool               `json:"highlight_missing_first_column"`
}

type StyleSpec struct {
	FontName     string `json:"font_name"`
	FontSize     int    `json:"font_size"`
	Bold         bool   `json:"bold"`
	Fill         string `json:"fill"`
	Horizontal   string `json:"horizontal"`
	Vertical     string `json:"vertical"`
	WrapText     bool   `json:"wrap_text"`
	Border       bool   `json:"border"`
	NumberFormat string `json:"number_format"`
}

type ColumnSpec struct {
	Column           string `json:"column"`
	Field            string `json:"field"`
	Header           string `json:"header"`
	Style            string `json:"style"`
	DataStyle        string `json:"data_style"`
	HeaderStyle      string `json:"header_style"`
	RequiredStyle    string `json:"required_style"`
	InstructionStyle string `json:"instruction_style"`
	Validation       string `json:"validation"`
	Default          any    `json:"default"`
	Required         string `json:"required"`
	Instruction      string `json:"instruction"`
}

// LoadSpec 加载模板 JSON。
func LoadSpec(templateDir, fileName string) (*ExcelSpec, *apperrors.AppError) {
	path := filepath.Join(templateDir, fileName)
	content, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, apperrors.New("EXPORT_TEMPLATE_MISSING",
				"Excel 导出模板缺失："+fileName+"，请检查后端代码目录 app/templates", 0,
				map[string]any{"template": fileName, "template_dir": templateDir})
		}
		return nil, apperrors.New("EXPORT_TEMPLATE_INVALID",
			"Excel 导出模板编码错误："+fileName, 0, map[string]any{"template": fileName})
	}
	var spec ExcelSpec
	if err := json.Unmarshal(content, &spec); err != nil {
		return nil, apperrors.New("EXPORT_TEMPLATE_INVALID",
			"Excel 导出模板格式错误："+fileName, 0, map[string]any{"template": fileName})
	}
	return &spec, nil
}

// CellValue 复刻 _cell_value：空值取默认、去非法字符、防公式注入。
func CellValue(row map[string]any, column ColumnSpec) any {
	value := row[column.Field]
	result := value
	if result == nil || result == "" {
		result = column.Default
	}
	if s, ok := result.(string); ok {
		s = illegalExcelChars.ReplaceAllString(s, "")
		if strings.HasPrefix(s, "=") || strings.HasPrefix(s, "+") || strings.HasPrefix(s, "-") || strings.HasPrefix(s, "@") {
			return "'" + s
		}
		return s
	}
	return result
}

func fillColor(color string) string {
	if color == "" {
		return ""
	}
	if strings.HasPrefix(color, "FF") {
		return color
	}
	return "FF" + color
}

func applyStyle(f *excelize.File, sheet, cell string, style StyleSpec) {
	alignment := &excelize.Alignment{
		Horizontal: style.Horizontal, Vertical: style.Vertical, WrapText: style.WrapText,
	}
	styleID, err := f.NewStyle(&excelize.Style{
		Font: &excelize.Font{
			Family: style.FontName, Size: float64(style.FontSize), Bold: style.Bold, Color: "#000000",
		},
		Alignment:    alignment,
		Fill:         excelize.Fill{Type: "pattern", Color: []string{fillColor(style.Fill)}, Pattern: 1},
		Border:       borderStyle(style.Border),
		CustomNumFmt: customNumFmt(style.NumberFormat),
	})
	if err == nil {
		_ = f.SetCellStyle(sheet, cell, cell, styleID)
	}
}

func customNumFmt(v string) *string {
	if v == "" {
		return nil
	}
	return &v
}

func borderStyle(enabled bool) []excelize.Border {
	if !enabled {
		return nil
	}
	return []excelize.Border{
		{Type: "left", Color: "000000", Style: 1}, {Type: "right", Color: "000000", Style: 1},
		{Type: "top", Color: "000000", Style: 1}, {Type: "bottom", Color: "000000", Style: 1},
	}
}

func setDimensions(f *excelize.File, sheet string, spec SheetSpec) {
	for col, width := range spec.ColumnWidths {
		_ = f.SetColWidth(sheet, col, col, width)
	}
	for row, height := range spec.RowHeights {
		_ = f.SetRowHeight(sheet, parseInt(row), height)
	}
}

func parseInt(s string) int {
	n := 0
	for _, r := range s {
		if r < '0' || r > '9' {
			break
		}
		n = n*10 + int(r-'0')
	}
	return n
}

// RenderTemplate 渲染模板导出（material-code-application / purchase-application / purchase-approval）。
func RenderTemplate(templateDir, templateFile string, rows []map[string]any) ([]byte, string, *apperrors.AppError) {
	spec, appErr := LoadSpec(templateDir, templateFile)
	if appErr != nil {
		return nil, "", appErr
	}
	f := excelize.NewFile()
	sheet := f.GetSheetName(0)
	_ = f.SetSheetName(sheet, spec.Sheet.Title)
	_ = f.SetSheetRow(sheet, "A1", []any{})
	setDimensions(f, sheet, spec.Sheet)
	if spec.Sheet.FreezePanes != "" {
		_ = f.SetPanes(sheet, &excelize.Panes{Freeze: true, XSplit: 1, YSplit: spec.Sheet.DataStartRow - 1, TopLeftCell: spec.Sheet.FreezePanes})
	}
	for _, merged := range spec.Sheet.MergedCells {
		_ = f.MergeCell(sheet, merged, merged)
	}
	if spec.Sheet.TitleCell != "" {
		_ = f.SetCellValue(sheet, spec.Sheet.TitleCell, spec.Sheet.Title)
		if s, ok := spec.Styles["title"]; ok {
			applyStyle(f, sheet, spec.Sheet.TitleCell, s)
		}
	}
	headerRow := spec.Sheet.HeaderRow
	requiredRow := spec.Sheet.RequiredRow
	instructionRow := spec.Sheet.InstructionRow
	if instructionRow > 0 {
		_ = f.SetCellValue(sheet, "B"+fmt.Sprint(instructionRow), "说明")
		if s, ok := spec.Styles["instruction"]; ok {
			applyStyle(f, sheet, "B"+fmt.Sprint(instructionRow), s)
		}
	}
	for _, column := range spec.Columns {
		letter := column.Column
		rowsMap := []struct {
			rowNo int
			key   string
			value string
		}{
			{headerRow, "header", column.Header},
			{requiredRow, "required", column.Required},
			{instructionRow, "instruction", column.Instruction},
		}
		for _, r := range rowsMap {
			if r.rowNo <= 0 {
				continue
			}
			cell := letter + fmt.Sprint(r.rowNo)
			_ = f.SetCellValue(sheet, cell, r.value)
			styleKey := r.key + "_style"
			if s, ok := spec.Styles[styleKey]; ok {
				applyStyle(f, sheet, cell, s)
			} else if s, ok := spec.Styles["instruction"]; ok {
				applyStyle(f, sheet, cell, s)
			}
		}
	}
	dataStart := spec.Sheet.DataStartRow
	minRows := spec.Sheet.MinimumDataRows
	if minRows < 1 {
		minRows = 1
	}
	dataRowCount := len(rows)
	if dataRowCount < minRows {
		dataRowCount = minRows
	}
	for offset := 0; offset < dataRowCount; offset++ {
		var row map[string]any
		if offset < len(rows) {
			row = rows[offset]
		} else {
			row = map[string]any{}
		}
		rowNo := dataStart + offset
		for _, column := range spec.Columns {
			cell := column.Column + fmt.Sprint(rowNo)
			_ = f.SetCellValue(sheet, cell, CellValue(row, column))
			styleKey := "data"
			if column.DataStyle != "" {
				styleKey = column.DataStyle
			} else if column.Style != "" {
				styleKey = column.Style
			}
			if s, ok := spec.Styles[styleKey]; ok {
				applyStyle(f, sheet, cell, s)
			}
		}
		_ = f.SetRowHeight(sheet, rowNo, 24)
	}
	setPrintArea(f, sheet, fmt.Sprintf("B2:AA%d", dataStart+dataRowCount-1))
	// 采购申请表：数据校验下拉 + 条件格式 + 自动筛选
	if spec.Sheet.HeaderRow > 0 && len(spec.Columns) > 0 && templateFile != "material-code-application.json" {
		lastColumn := columnLetter(len(spec.Columns))
		lastRow := dataStart + len(rows) - 1
		if lastRow < dataStart {
			lastRow = dataStart
		}
		for _, column := range spec.Columns {
			if column.Validation == "" {
				continue
			}
			options := spec.ValidationLists[column.Validation]
			dv := excelize.NewDataValidation(true)
			dv.Sqref = fmt.Sprintf("%s%d:%s%d", column.Column, dataStart, column.Column, lastRow)
			_ = dv.SetDropList(options)
			_ = f.AddDataValidation(sheet, dv)
		}
		if spec.Sheet.HighlightMissingFirstColumn && len(rows) > 0 {
			_ = f.SetConditionalFormat(sheet, fmt.Sprintf("A%d:%s%d", dataStart, lastColumn, lastRow),
				[]excelize.ConditionalFormatOptions{
					{Type: "expression", Criteria: fmt.Sprintf("LEN($A%d)=0", dataStart)},
				})
		}
		_ = f.AutoFilter(sheet, fmt.Sprintf("A%d:%s%d", headerRow, lastColumn, lastRow), nil)
		setPrintArea(f, sheet, fmt.Sprintf("A%d:%s%d", headerRow, lastColumn, lastRow))
	}
	buf, err := f.WriteToBuffer()
	if err != nil {
		return nil, "", apperrors.New("EXPORT_RENDER_ERROR", "Excel 渲染失败", 0, nil)
	}
	filename := spec.OutputFilename
	if filename == "" {
		filename = "export.xlsx"
	}
	return buf.Bytes(), filename, nil
}

func columnLetter(n int) string {
	letters := ""
	for n > 0 {
		n--
		letters = string(rune('A'+n%26)) + letters
		n /= 26
	}
	return letters
}

// RenderResultExcel 结果导出（动态列 + 图片）。
func RenderResultExcel(title string, columns [][2]string, rows []map[string]any) ([]byte, string, *apperrors.AppError) {
	f := excelize.NewFile()
	sheet := f.GetSheetName(0)
	_ = f.SetSheetName(sheet, title)
	headerStyle, _ := f.NewStyle(&excelize.Style{
		Font:      &excelize.Font{Bold: true, Family: "等线", Size: 11, Color: "#000000"},
		Fill:      excelize.Fill{Type: "pattern", Color: []string{"FFD9EAD3"}, Pattern: 1},
		Alignment: &excelize.Alignment{Horizontal: "center", Vertical: "center", WrapText: true},
		Border:    allBorders(),
	})
	dataStyle, _ := f.NewStyle(&excelize.Style{
		Font:      &excelize.Font{Family: "等线", Size: 11, Color: "#000000"},
		Alignment: &excelize.Alignment{Horizontal: "center", Vertical: "center", WrapText: true},
		Border:    allBorders(),
	})
	for i, col := range columns {
		cell, _ := excelize.CoordinatesToCellName(i+1, 1)
		_ = f.SetCellValue(sheet, cell, col[1])
		_ = f.SetCellStyle(sheet, cell, cell, headerStyle)
		_ = f.SetColWidth(sheet, columnLetter(i+1), columnLetter(i+1), displayWidth(col[1]))
	}
	_ = f.SetRowHeight(sheet, 1, 30)
	for ri, row := range rows {
		rowNo := ri + 2
		for ci, col := range columns {
			cell, _ := excelize.CoordinatesToCellName(ci+1, rowNo)
			value := CellValue(row, ColumnSpec{Field: col[0]})
			// 图片列表 -> 嵌入缩略图
			if imgs, ok := row[col[0]].([]string); ok {
				_ = f.SetCellValue(sheet, cell, "")
				embedRowImages(f, sheet, cell, imgs)
			} else {
				_ = f.SetCellValue(sheet, cell, value)
			}
			_ = f.SetCellStyle(sheet, cell, cell, dataStyle)
		}
		_ = f.SetRowHeight(sheet, rowNo, 24)
	}
	buf, err := f.WriteToBuffer()
	if err != nil {
		return nil, "", apperrors.New("EXPORT_RENDER_ERROR", "Excel 渲染失败", 0, nil)
	}
	filename := title + ".xlsx"
	return buf.Bytes(), filename, nil
}

// embedRowImages 在单元格右侧嵌入图片（约 96px）。
func embedRowImages(f *excelize.File, sheet, cell string, paths []string) {
	for i, p := range paths {
		imgPath := p
		if _, err := os.Stat(imgPath); err != nil {
			continue
		}
		if err := f.AddPicture(sheet, cell, imgPath, &excelize.GraphicOptions{
			ScaleX: 0.5, ScaleY: 0.5, OffsetX: 5 + i*0, Positioning: "oneCell",
		}); err != nil {
			continue
		}
	}
}

func allBorders() []excelize.Border {
	return []excelize.Border{
		{Type: "left", Color: "000000", Style: 1}, {Type: "right", Color: "000000", Style: 1},
		{Type: "top", Color: "000000", Style: 1}, {Type: "bottom", Color: "000000", Style: 1},
	}
}

func displayWidth(label string) float64 {
	// 近似东亚宽度：中文字符计 2
	width := float64(0)
	for _, r := range label {
		if r > 0x2E7F {
			width += 2
		} else {
			width += 1
		}
	}
	if width < 10 {
		width = 10
	}
	return width + 4
}

// WriteExportFile 原子写入（先 .tmp 再改名）。
func WriteExportFile(target string, content []byte) error {
	tmp := target + ".tmp"
	if err := os.WriteFile(tmp, content, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, target)
}

// ContentDisposition 构造 RFC5987 文件名头。
func ContentDisposition(filename string) string {
	return "attachment; filename*=UTF-8''" + url.QueryEscape(filename)
}

func setPrintArea(f *excelize.File, sheet, area string) {
	_ = f.SetDefinedName(&excelize.DefinedName{Name: "_xlnm.Print_Area", RefersTo: area, Scope: sheet})
}
