package excel_test

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/xuri/excelize/v2"

	"github.com/yangrucheng/materials-manager/server/internal/excel"
)

func TestReadXLSX(t *testing.T) {
	f := excelize.NewFile()
	defer f.Close()
	sheet := "Sheet1"
	f.SetCellValue(sheet, "A1", "编码")
	f.SetCellValue(sheet, "B1", "名称")
	f.SetCellValue(sheet, "A2", "M1001")
	f.SetCellValue(sheet, "B2", "交流接触器")
	f.SetCellValue(sheet, "A3", "M1002")
	path := filepath.Join(t.TempDir(), "codes.xlsx")
	if err := f.SaveAs(path); err != nil {
		t.Fatal(err)
	}
	rows, appErr := excel.ReadTabularRows(path)
	if appErr != nil {
		t.Fatal(appErr)
	}
	if len(rows) != 3 {
		t.Fatalf("rows=%d", len(rows))
	}
	if rows[0][0] != "编码" || rows[1][0] != "M1001" {
		t.Fatalf("rows=%v", rows)
	}
	if len(rows[2]) > 1 && rows[2][1] != "" {
		t.Fatalf("第三行 B 列应为空: %v", rows[2])
	}
}

func TestReadCSVUTF8(t *testing.T) {
	path := filepath.Join(t.TempDir(), "codes.csv")
	content := "编码,名称,型号\nM1,断路器,DZ47\nM2,接触器,CJX2\n"
	if err := os.WriteFile(path, []byte("\ufeff"+content), 0o644); err != nil {
		t.Fatal(err)
	}
	rows, appErr := excel.ReadTabularRows(path)
	if appErr != nil {
		t.Fatal(appErr)
	}
	if len(rows) != 3 || rows[1][0] != "M1" || rows[2][0] != "M2" {
		t.Fatalf("rows=%v", rows)
	}
}

func TestUnsupportedSuffix(t *testing.T) {
	path := filepath.Join(t.TempDir(), "data.txt")
	_ = os.WriteFile(path, []byte("x"), 0o644)
	_, appErr := excel.ReadTabularRows(path)
	if appErr == nil || appErr.Code != "UNSUPPORTED_EXCEL_FILE" {
		t.Fatalf("appErr=%v", appErr)
	}
}

// TestReadXLSNumericFormats 回归（华星 job#14）：.xls 中 RK 存储、带用户自定义数字格式的
// 数量单元格不得被渲染成日期串；日期格式单元格必须渲染为可解析日期。
func TestReadXLSNumericFormats(t *testing.T) {
	rows, appErr := excel.ReadTabularRows(filepath.Join("testdata", "huaxing_rk_formatted.xls"))
	if appErr != nil {
		t.Fatal(appErr)
	}
	if len(rows) < 3 {
		t.Fatalf("rows=%d", len(rows))
	}
	if got := fmt.Sprint(rows[1][5]); got != "1" {
		t.Fatalf("带自定义数字格式的数量应为原始数字 1，实际 %q", got)
	}
	if got := fmt.Sprint(rows[2][5]); got != "2" {
		t.Fatalf("数量应为 2，实际 %q", got)
	}
	if got := fmt.Sprint(rows[1][0]); got != "2026-08-30" {
		t.Fatalf("日期单元格应为 2026-08-30，实际 %q", got)
	}
}

// TestReadXLSFormulaCachedResults 回归：FORMULA 单元格解码缓存结果（数字/日期），
// 不再输出字面量 "FormulaCol" 或空值。
func TestReadXLSFormulaCachedResults(t *testing.T) {
	rows, appErr := excel.ReadTabularRows(filepath.Join("testdata", "huaxing_formula_cached.xls"))
	if appErr != nil {
		t.Fatal(appErr)
	}
	if got := fmt.Sprint(rows[1][5]); got != "2" {
		t.Fatalf("公式数量应解码缓存结果 2，实际 %q", got)
	}
	if got := fmt.Sprint(rows[1][0]); got != "2026-08-30" {
		t.Fatalf("日期公式应解码为 2026-08-30，实际 %q", got)
	}
}
