package excel_test

import (
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
