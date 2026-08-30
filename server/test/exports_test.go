package test

import (
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/gin-gonic/gin"

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
}

var _ = gin.Mode
