package test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/xuri/excelize/v2"

	"github.com/yangrucheng/materials-manager/server/internal/service"
	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

func TestExportUncodedTemplate(t *testing.T) {
	r := newTestEngine(t)
	purchase := login(t, r, "purchase")
	id, _ := createPlan(t, r, purchase, "未编码导出")
	_ = id
	w := testutil.Do(t, r, "GET", "/api/v1/purchase-materials/export-uncoded", purchase)
	if w.Code != 200 {
		t.Fatalf("export-uncoded status=%d body=%s", w.Code, w.Body.String())
	}
	if len(w.Body.Bytes()) == 0 {
		t.Fatal("导出内容为空")
	}
	if w.Header().Get("Content-Disposition") == "" {
		t.Fatal("缺少 Content-Disposition")
	}
}

func TestExportPurchaseApplicationTemplate(t *testing.T) {
	r := newTestEngine(t)
	purchase := login(t, r, "purchase")
	id, _ := createPlan(t, r, purchase, "采购申请导出")
	// 需要编码/子项号/用途
	doJSON(t, r, "PATCH", fmt.Sprintf("/api/v1/purchase-materials/%d", id),
		map[string]any{"name": "采购申请导出", "model_spec": "E-1", "unit_name": "个", "planned_qty": "5",
			"usage": "导出测试", "material_code": "M-E1", "subitem_no": "S-1", "urgency": "正常",
			"demand_department": "HXNI 检修维护部", "actual_demand_person": "张三",
			"purchase_responsible": "李四", "image_ids": []any{}, "version": 1}, purchase)
	w := doJSON(t, r, "POST", "/api/v1/purchase-materials/export-purchase-application",
		map[string]any{"material_ids": []any{id}}, purchase)
	if w.Code != 200 {
		t.Fatalf("export-purchase-application status=%d body=%s", w.Code, w.Body.String())
	}
	// 缺编码 -> 409
	badID, _ := createPlan(t, r, purchase, "缺编码导出")
	_ = badID
	w2 := doJSON(t, r, "POST", "/api/v1/purchase-materials/export-purchase-application",
		map[string]any{"material_ids": []any{badID}}, purchase)
	if w2.Code != 409 {
		t.Fatalf("缺字段应 409, status=%d body=%s", w2.Code, w2.Body.String())
	}
}

func TestExportResultsJobAndDownload(t *testing.T) {
	r := newTestEngine(t)
	purchase := login(t, r, "purchase")
	createPlan(t, r, purchase, "结果导出A")
	createPlan(t, r, purchase, "结果导出B")
	w := doJSON(t, r, "POST", "/api/v1/purchase-materials/export-results",
		map[string]any{"columns": []any{"plan_no", "name", "planned_qty", "usage"}}, purchase)
	if w.Code != 202 {
		t.Fatalf("export-results status=%d body=%s", w.Code, w.Body.String())
	}
	var job map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &job)
	jobID := int64(job["id"].(float64))
	deadline := time.Now().Add(5 * time.Second)
	var done map[string]any
	for time.Now().Before(deadline) {
		jw := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/excel-export-jobs/%d", jobID), purchase)
		var j map[string]any
		_ = json.Unmarshal(jw.Body.Bytes(), &j)
		if j["status"] == "SUCCEEDED" || j["status"] == "FAILED" {
			done = j
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if done == nil || done["status"] != "SUCCEEDED" {
		t.Fatalf("export job 未完成: %v", done)
	}
	// 匿名下载
	filename := done["download_filename"].(string)
	fileUUID := done["file_uuid"].(string)
	_ = filename
	dl := testutil.Do(t, r, "GET", "/api/v1/excel-export-jobs/files/"+fileUUID, nil)
	if dl.Code != 200 {
		t.Fatalf("download status=%d body=%s", dl.Code, dl.Body.String())
	}
	if len(dl.Body.Bytes()) == 0 {
		t.Fatal("下载内容为空")
	}
	// 回归：解析 xlsx，必须包含表头与至少一行数据（防"空表"回归）
	f, err := excelize.OpenReader(bytes.NewReader(dl.Body.Bytes()))
	if err != nil {
		t.Fatalf("解析导出 xlsx 失败: %v", err)
	}
	defer f.Close()
	rows, err := f.GetRows(f.GetSheetList()[0])
	if err != nil {
		t.Fatalf("读取导出 sheet 失败: %v", err)
	}
	if len(rows) < 2 {
		t.Fatalf("导出为空表：仅 %d 行（应含表头+数据）", len(rows))
	}
	if rows[1][0] == "" {
		t.Fatalf("导出数据行首列空: %v", rows[1])
	}
}

// 回归：前端传状态 VALUE（中文"正常"），后端须转 NAME（NORMAL）再查询，
// 否则 WHERE status IN ('正常') 查不到任何行 → 导出空表（rows=0）。
func TestExportResultsStatusValueConversion(t *testing.T) {
	r := newTestEngine(t)
	purchase := login(t, r, "purchase")
	id, _ := createPlan(t, r, purchase, "状态导出计划")
	doJSON(t, r, "PATCH", fmt.Sprintf("/api/v1/purchase-materials/%d", id),
		map[string]any{"name": "状态导出计划", "model_spec": "S-1", "unit_name": "个", "planned_qty": "5",
			"usage": "状态导出", "material_code": "M-S1", "subitem_no": "S-S1", "urgency": "正常",
			"demand_department": "HXNI 检修维护部", "actual_demand_person": "张三",
			"purchase_responsible": "李四", "image_ids": []any{}, "version": 1}, purchase)
	w := doJSON(t, r, "POST", "/api/v1/purchase-materials/export-results",
		map[string]any{"columns": []any{"plan_no", "name"}, "status": []any{"正常"}}, purchase)
	if w.Code != 202 {
		t.Fatalf("export-results status=%d body=%s", w.Code, w.Body.String())
	}
	var job map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &job)
	jobID := int64(job["id"].(float64))
	deadline := time.Now().Add(5 * time.Second)
	var done map[string]any
	for time.Now().Before(deadline) {
		jw := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/excel-export-jobs/%d", jobID), purchase)
		var j map[string]any
		_ = json.Unmarshal(jw.Body.Bytes(), &j)
		if j["status"] == "SUCCEEDED" || j["status"] == "FAILED" {
			done = j
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if done == nil || done["status"] != "SUCCEEDED" {
		t.Fatalf("导出任务未成功: %v", done)
	}
	res, _ := done["result"].(map[string]any)
	if rows, _ := res["rows"].(float64); rows < 1 {
		t.Fatalf("导出 rows=%v，状态 VALUE 未转 NAME 会导致查不到数据", res["rows"])
	}
	dl := testutil.Do(t, r, "GET", "/api/v1/excel-export-jobs/files/"+done["file_uuid"].(string), nil)
	f, err := excelize.OpenReader(bytes.NewReader(dl.Body.Bytes()))
	if err != nil {
		t.Fatalf("解析导出 xlsx 失败: %v", err)
	}
	defer f.Close()
	rows, err := f.GetRows(f.GetSheetList()[0])
	if err != nil {
		t.Fatalf("读取导出 sheet 失败: %v", err)
	}
	if len(rows) < 2 {
		t.Fatalf("导出为空表：仅 %d 行（状态 VALUE 导出应有数据）", len(rows))
	}
}

// 回归：导出任务/文件须按保留期清理（3 天），防磁盘无限增长。
// 曾因 Go 重构未接线清理函数，导出文件永不删除。
func TestExportCleanupRetention(t *testing.T) {
	cfg := testutil.NewTestConfig(t)
	db := testutil.OpenTestDB(t, cfg)

	// 构造两个导出任务：一个 4 天前完成（过期）、一个刚完成（保留）
	write := func(id int64, status, finishedAt string, file string) {
		if err := db.Exec(
			`INSERT INTO excel_export_job (id, export_type, status, download_filename, file_path, result, created_at, updated_at, finished_at)
			 VALUES (?, 'PURCHASE_PLAN_RESULTS', ?, NULL, ?, NULL, ?, ?, ?)`,
			id, status, file, finishedAt, finishedAt, finishedAt,
		).Error; err != nil {
			t.Fatalf("插入任务失败: %v", err)
		}
	}
	old := time.Now().UTC().Add(-4 * 24 * time.Hour).Format("2006-01-02 15:04:05")
	now := time.Now().UTC().Format("2006-01-02 15:04:05")
	write(1, "SUCCEEDED", old, "/tmp/exports/old-file.xlsx")
	write(2, "SUCCEEDED", now, "/tmp/exports/new-file.xlsx")

	// 造对应文件
	os.MkdirAll("/tmp/exports", 0o755)
	os.WriteFile("/tmp/exports/old-file.xlsx", []byte("old"), 0o644)
	os.WriteFile("/tmp/exports/new-file.xlsx", []byte("new"), 0o644)

	// 清理后：旧任务（1）应被删除，新任务（2）保留
	n := service.CleanupFinishedExports(cfg, db)
	if n < 1 {
		t.Fatalf("应清理 >=1 个过期导出任务，实际 %d", n)
	}
	var cnt int64
	db.Table("excel_export_job").Where("id = 1").Count(&cnt)
	if cnt != 0 {
		t.Fatalf("过期任务 id=1 应被删除，仍存在 %d 条", cnt)
	}
	db.Table("excel_export_job").Where("id = 2").Count(&cnt)
	if cnt != 1 {
		t.Fatalf("新任务 id=2 应保留，实际 %d 条", cnt)
	}
	if _, err := os.Stat("/tmp/exports/old-file.xlsx"); err == nil {
		t.Fatal("过期文件应被删除")
	}
	if _, err := os.Stat("/tmp/exports/new-file.xlsx"); err != nil {
		t.Fatal("新文件应保留")
	}
	// 清理测试残留文件
	os.RemoveAll("/tmp/exports")
}

var _ = gin.Mode
