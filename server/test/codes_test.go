package test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"mime/multipart"
	"net/http/httptest"
	"net/textproto"
	"path/filepath"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/xuri/excelize/v2"

	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

func uploadImport(t *testing.T, r *gin.Engine, headers map[string]string, path string, filename string, data []byte) *httptest.ResponseRecorder {
	t.Helper()
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	h := make(textproto.MIMEHeader)
	h.Set("Content-Disposition", fmt.Sprintf(`form-data; name="file"; filename="%s"`, filename))
	h.Set("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	part, err := writer.CreatePart(h)
	if err != nil {
		t.Fatal(err)
	}
	_, _ = part.Write(data)
	_ = writer.Close()
	req := httptest.NewRequest("POST", path, &body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func makeImportXLSX(t *testing.T, header []string, rows [][]string) []byte {
	t.Helper()
	f := excelize.NewFile()
	defer f.Close()
	sheet := "Sheet1"
	for i, h := range header {
		cell, _ := excelize.CoordinatesToCellName(i+1, 1)
		_ = f.SetCellValue(sheet, cell, h)
	}
	for ri, row := range rows {
		for ci, v := range row {
			cell, _ := excelize.CoordinatesToCellName(ci+1, ri+2)
			_ = f.SetCellValue(sheet, cell, v)
		}
	}
	var buf bytes.Buffer
	if err := f.Write(&buf); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func waitImportDone(t *testing.T, r *gin.Engine, headers map[string]string, jobID int64) map[string]any {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		w := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/material-code-library/import-jobs/%d", jobID), headers)
		if w.Code != 200 {
			t.Fatalf("job status=%d body=%s", w.Code, w.Body.String())
		}
		var job map[string]any
		_ = json.Unmarshal(w.Body.Bytes(), &job)
		if job["status"] == "SUCCEEDED" || job["status"] == "FAILED" {
			return job
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatal("导入任务未在 5s 内完成")
	return nil
}

func TestMaterialCodeImport(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	xlsx := makeImportXLSX(t, []string{"编码", "名称", "型号", "记账单位名称"},
		[][]string{{"M-001", "断路器", "DZ47", "个"}, {"M-002", "接触器", "CJX2", "个"}})
	w := uploadImport(t, r, warehouse, "/api/v1/material-code-library/import", "codes.xlsx", xlsx)
	if w.Code != 202 {
		t.Fatalf("import status=%d body=%s", w.Code, w.Body.String())
	}
	var job map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &job)
	jobID := int64(job["id"].(float64))
	done := waitImportDone(t, r, warehouse, jobID)
	if done["status"] != "SUCCEEDED" {
		t.Fatalf("job failed: %v", done)
	}
	result := done["result"].(map[string]any)
	if int(result["imported_count"].(float64)) != 2 {
		t.Fatalf("imported_count=%v", result)
	}
	// 列表
	list := testutil.Do(t, r, "GET", "/api/v1/material-code-library?page=1&page_size=20", warehouse)
	var page map[string]any
	_ = json.Unmarshal(list.Body.Bytes(), &page)
	if int(page["total"].(float64)) != 2 {
		t.Fatalf("total=%v", page["total"])
	}
	// exists
	exists := testutil.Do(t, r, "GET", "/api/v1/material-code-library/exists?material_code=M-001", warehouse)
	var ex map[string]any
	_ = json.Unmarshal(exists.Body.Bytes(), &ex)
	if ex["exists"] != true {
		t.Fatalf("exists=%v", ex)
	}
}

func TestMaterialCodeImportValidation(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	// 缺列
	xlsx := makeImportXLSX(t, []string{"编码", "名称"}, [][]string{{"M-1", "断路器"}})
	w := uploadImport(t, r, warehouse, "/api/v1/material-code-library/import", "bad.xlsx", xlsx)
	var job map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &job)
	done := waitImportDone(t, r, warehouse, int64(job["id"].(float64)))
	if done["status"] != "FAILED" {
		t.Fatalf("缺列应失败: %v", done)
	}
	if done["error_code"] != "MATERIAL_CODE_IMPORT_HEADERS_MISSING" {
		t.Fatalf("error_code=%v", done["error_code"])
	}
}

func TestHuaXingAndLiteImport(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	// 华兴导入
	hx := makeImportXLSX(t, []string{"首次入库日期", "仓库", "货品编码", "货品名称", "型号", "数量", "单位", "申购人", "申购部门", "子项号名称"},
		[][]string{{"2026-07-01", "主仓", "H-1", "电机", "M1", "2", "台", "张三", "部门A", "S1"}})
	w := uploadImport(t, r, warehouse, "/api/v1/huaxing-inventory/import", "hx.xlsx", hx)
	var job map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &job)
	done := waitImportDone2(t, r, warehouse, "/api/v1/huaxing-inventory/import-jobs/", int64(job["id"].(float64)))
	if done["status"] != "SUCCEEDED" {
		t.Fatalf("huaxing import failed: %v", done)
	}
	// 华兴列表
	hl := testutil.Do(t, r, "GET", "/api/v1/huaxing-inventory?page=1&page_size=20", warehouse)
	var hp map[string]any
	_ = json.Unmarshal(hl.Body.Bytes(), &hp)
	if int(hp["total"].(float64)) != 1 {
		t.Fatalf("huaxing total=%v", hp["total"])
	}

	// 精简二级库导入
	li := makeImportXLSX(t, []string{"物资名称", "型号规格", "单位", "数量", "备注"},
		[][]string{{"灯泡", "LED", "个", "50", "常备"}})
	w2 := uploadImport(t, r, warehouse, "/api/v1/secondary-warehouse/import", "lite.xlsx", li)
	var job2 map[string]any
	_ = json.Unmarshal(w2.Body.Bytes(), &job2)
	done2 := waitImportDone2(t, r, warehouse, "/api/v1/secondary-warehouse/import-jobs/", int64(job2["id"].(float64)))
	if done2["status"] != "SUCCEEDED" {
		t.Fatalf("lite import failed: %v", done2)
	}
	ll := testutil.Do(t, r, "GET", "/api/v1/secondary-warehouse?page=1&page_size=20", warehouse)
	var lp map[string]any
	_ = json.Unmarshal(ll.Body.Bytes(), &lp)
	if int(lp["total"].(float64)) != 1 {
		t.Fatalf("lite total=%v", lp["total"])
	}
	// last-import
	last := testutil.Do(t, r, "GET", "/api/v1/material-code-library/last-import", warehouse)
	if last.Code != 200 {
		t.Fatalf("last-import status=%d", last.Code)
	}
}

func waitImportDone2(t *testing.T, r *gin.Engine, headers map[string]string, prefix string, jobID int64) map[string]any {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		w := testutil.Do(t, r, "GET", fmt.Sprintf("%s%d", prefix, jobID), headers)
		if w.Code != 200 {
			t.Fatalf("job status=%d body=%s", w.Code, w.Body.String())
		}
		var job map[string]any
		_ = json.Unmarshal(w.Body.Bytes(), &job)
		if job["status"] == "SUCCEEDED" || job["status"] == "FAILED" {
			return job
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatal("导入任务未在 5s 内完成")
	return nil
}

var _ = filepath.Join
var _ = gin.Mode
