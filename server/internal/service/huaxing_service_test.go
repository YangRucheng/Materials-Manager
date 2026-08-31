package service

import (
	"github.com/shopspring/decimal"
	"path/filepath"
	"testing"
)

func TestNormalizeNumberText(t *testing.T) {
	cases := map[string]string{
		"1234":     "1234",
		"1,234":    "1234",
		"1，234":    "1234",
		"1,234.5":  "1234.5",
		"1 234":    "1234",
		"１２３":      "123",
		"１，２":      "12",
		"(1,234)":  "-1234",
		"（1234）":   "-1234",
		"1.05E+03": "1.05E+03",
		"-42":      "-42",
		"  5  ":    "5",
	}
	for in, want := range cases {
		if got := normalizeNumberText(in); got != want {
			t.Errorf("normalizeNumberText(%q)=%q, want %q", in, got, want)
		}
	}
}

func TestCellQuantityNormalization(t *testing.T) {
	q, appErr := cellQuantity("1,234", 2)
	if appErr != nil {
		t.Fatal(appErr)
	}
	if q == nil || !q.Equal(decimal.NewFromInt(1234)) {
		t.Fatalf("q=%v", q)
	}
	// 非法值：报错信息须携带原始值，便于远程定位（华星 job#14）。
	_, appErr = cellQuantity("FormulaCol", 2)
	if appErr == nil {
		t.Fatal("expected error")
	}
	if appErr.Code != "HUAXING_IMPORT_INVALID_QUANTITY" {
		t.Fatalf("code=%s", appErr.Code)
	}
	if want := "第 2 行数量 \"FormulaCol\" 不是有效数值"; appErr.Message != want {
		t.Fatalf("msg=%q want %q", appErr.Message, want)
	}
}

// TestParseHuaXingFileRKRegression 端到端复现华星 job#14：
// 数量以 RK 存储、单元格带用户自定义数字格式（如会计 0_);(0)），
// 旧 reader 会把它渲染成 "1899-12-31T00:00:00Z" 之类日期串导致解析失败。
func TestParseHuaXingFileRKRegression(t *testing.T) {
	rows, appErr := ParseHuaXingFile(filepath.Join("..", "excel", "testdata", "huaxing_rk_formatted.xls"))
	if appErr != nil {
		t.Fatal(appErr)
	}
	if len(rows) != 2 {
		t.Fatalf("rows=%d", len(rows))
	}
	if rows[0].Quantity == nil || !rows[0].Quantity.Equal(decimal.NewFromInt(1)) {
		t.Fatalf("第 1 行数量应为 1，实际 %v", rows[0].Quantity)
	}
	if rows[0].MaterialCode != "703419746152" {
		t.Fatalf("货品编码错位: %q", rows[0].MaterialCode)
	}
	if rows[0].FirstInboundDate == nil {
		t.Fatal("首次入库日期不应为空")
	}
}

// TestParseHuaXingFileFormulaRegression：数量/日期为公式且有缓存结果。
func TestParseHuaXingFileFormulaRegression(t *testing.T) {
	rows, appErr := ParseHuaXingFile(filepath.Join("..", "excel", "testdata", "huaxing_formula_cached.xls"))
	if appErr != nil {
		t.Fatal(appErr)
	}
	if len(rows) != 1 {
		t.Fatalf("rows=%d", len(rows))
	}
	if rows[0].Quantity == nil || !rows[0].Quantity.Equal(decimal.NewFromInt(2)) {
		t.Fatalf("公式数量应为 2，实际 %v", rows[0].Quantity)
	}
}

// TestParseHuaXingFileMergedTitle：第 1 行为合并单元格标题、第 2 行才是表头。
func TestParseHuaXingFileMergedTitle(t *testing.T) {
	rows, appErr := ParseHuaXingFile(filepath.Join("..", "excel", "testdata", "huaxing_merged_title.xls"))
	if appErr != nil {
		t.Fatal(appErr)
	}
	if len(rows) != 1 || rows[0].MaterialCode != "703419746152" {
		t.Fatalf("rows=%+v", rows)
	}
	if rows[0].Quantity == nil || !rows[0].Quantity.Equal(decimal.NewFromInt(3)) {
		t.Fatalf("数量应为 3，实际 %v", rows[0].Quantity)
	}
}
