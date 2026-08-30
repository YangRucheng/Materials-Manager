package test

import (
	"encoding/json"
	"fmt"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

// createPlan 创建申购计划，返回 id 与 plan_no。
func createPlan(t *testing.T, r *gin.Engine, headers map[string]string, name string) (int64, string) {
	t.Helper()
	payload := map[string]any{
		"name": name, "model_spec": "SPEC-1", "unit_name": "个",
		"planned_qty": "10", "usage": "现场维护", "urgency": "正常",
		"demand_department":    "HXNI 检修维护部",
		"actual_demand_person": "张三", "purchase_responsible": "李四",
		"image_ids": []any{},
	}
	w := doJSON(t, r, "POST", "/api/v1/purchase-materials", payload, headers)
	if w.Code != 201 {
		t.Fatalf("create plan status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	return int64(body["id"].(float64)), body["plan_no"].(string)
}

func TestPurchaseMaterialCRUD(t *testing.T) {
	r := newTestEngine(t)
	purchase := login(t, r, "purchase")
	id, planNo := createPlan(t, r, purchase, "断路器")

	// 列表
	list := testutil.Do(t, r, "GET", "/api/v1/purchase-materials?page=1&page_size=20", purchase)
	var page map[string]any
	_ = json.Unmarshal(list.Body.Bytes(), &page)
	if int(page["total"].(float64)) != 1 {
		t.Fatalf("total=%v body=%s", page["total"], list.Body.String())
	}
	first := page["items"].([]any)[0].(map[string]any)
	if first["status"] != "正常" || first["planned_qty"] != "10" || first["moved_to_record"] != false {
		t.Fatalf("计划字段错误: %v", first)
	}
	if planNo[:5] != "PLAN-" {
		t.Fatalf("plan_no=%q", planNo)
	}

	// 详情
	detail := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/purchase-materials/%d", id), purchase)
	if detail.Code != 200 {
		t.Fatalf("detail status=%d", detail.Code)
	}

	// 更新
	update := doJSON(t, r, "PATCH", fmt.Sprintf("/api/v1/purchase-materials/%d", id),
		map[string]any{"name": "断路器改", "model_spec": "SPEC-2", "unit_name": "个", "planned_qty": "15",
			"usage": "现场维护", "urgency": "正常", "demand_department": "HXNI 检修维护部",
			"actual_demand_person": "张三", "purchase_responsible": "李四", "image_ids": []any{}, "version": 1}, purchase)
	if update.Code != 200 {
		t.Fatalf("update status=%d body=%s", update.Code, update.Body.String())
	}
	var upd map[string]any
	_ = json.Unmarshal(update.Body.Bytes(), &upd)
	if upd["name"] != "断路器改" || upd["planned_qty"] != "15" {
		t.Fatalf("update 结果错误: %v", upd)
	}

	// 删除
	del := testutil.Do(t, r, "DELETE", fmt.Sprintf("/api/v1/purchase-materials/%d", id),
		map[string]string{"Authorization": purchase["Authorization"], "If-Match": "2"})
	if del.Code != 204 {
		t.Fatalf("delete status=%d body=%s", del.Code, del.Body.String())
	}
}

func TestMoveToRecordAndRestore(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "purchase")
	id, _ := createPlan(t, r, warehouse, "转记录物资")

	// 未编码转入 -> 409
	noCode := doJSON(t, r, "POST", "/api/v1/purchase-materials/batch-move-to-record",
		map[string]any{"materials": []any{map[string]any{"id": id, "version": 1}}}, warehouse)
	if noCode.Code != 409 {
		t.Fatalf("未编码转入应 409, status=%d body=%s", noCode.Code, noCode.Body.String())
	}

	// 关联编码（转记录要求有编码）
	doJSON(t, r, "PATCH", fmt.Sprintf("/api/v1/purchase-materials/%d", id),
		map[string]any{"name": "转记录物资", "model_spec": "SPEC-1", "unit_name": "个", "planned_qty": "10",
			"usage": "现场维护", "material_code": "M-001", "urgency": "正常",
			"demand_department": "HXNI 检修维护部", "actual_demand_person": "张三",
			"purchase_responsible": "李四", "image_ids": []any{}, "version": 1}, warehouse)

	// 现在有编码，转记录（version 应为 2：一次创建 + 一次补编码）
	move := doJSON(t, r, "POST", "/api/v1/purchase-materials/batch-move-to-record",
		map[string]any{"materials": []any{map[string]any{"id": id, "version": 2}}}, warehouse)
	if move.Code != 200 {
		t.Fatalf("move status=%d body=%s", move.Code, move.Body.String())
	}
	var moved []map[string]any
	_ = json.Unmarshal(move.Body.Bytes(), &moved)
	lineID := int64(moved[0]["line_id"].(float64))
	if moved[0]["material_name"] != "转记录物资" || moved[0]["status"] != "已申购" {
		t.Fatalf("记录快照错误: %v", moved[0])
	}

	// 计划已归档（仅超管可查）
	admin := login(t, r, "admin")
	detail := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/purchase-materials/%d", id), admin)
	var planBody map[string]any
	_ = json.Unmarshal(detail.Body.Bytes(), &planBody)
	if planBody["status"] != "已归档" {
		t.Fatalf("计划应归档: %v body=%s", planBody, detail.Body.String())
	}
	// 非超管查询已归档 -> 403
	forbidden := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/purchase-materials/%d", id), warehouse)
	if forbidden.Code != 403 {
		t.Fatalf("非超管查已归档应 403, status=%d", forbidden.Code)
	}

	// 记录列表
	records := testutil.Do(t, r, "GET", "/api/v1/purchase-records?page=1&page_size=20", warehouse)
	var recPage map[string]any
	_ = json.Unmarshal(records.Body.Bytes(), &recPage)
	if int(recPage["total"].(float64)) != 1 {
		t.Fatalf("records total=%v", recPage["total"])
	}

	// 记录回撤为计划
	restore := testutil.Do(t, r, "POST", fmt.Sprintf("/api/v1/purchase-records/%d/restore-to-plan", lineID),
		map[string]string{"Authorization": warehouse["Authorization"]})
	if restore.Code != 200 {
		t.Fatalf("restore status=%d body=%s", restore.Code, restore.Body.String())
	}
	var restored map[string]any
	_ = json.Unmarshal(restore.Body.Bytes(), &restored)
	if restored["status"] != "正常" || restored["plan_no"].(string)[:5] != "PLAN-" {
		t.Fatalf("restored=%v", restored)
	}
}

func TestPlanTemplateGenerate(t *testing.T) {
	r := newTestEngine(t)
	purchase := login(t, r, "purchase")
	create := doJSON(t, r, "POST", "/api/v1/purchase-plan-templates",
		map[string]any{"name": "周期模板", "model_spec": "T-1", "unit_name": "个", "planned_qty": "5",
			"usage": "周期性需求", "actual_demand_person": "张三", "purchase_responsible": "李四",
			"urgency": "正常", "demand_department": "HXNI 检修维护部", "image_ids": []any{}}, purchase)
	if create.Code != 201 {
		t.Fatalf("create template status=%d body=%s", create.Code, create.Body.String())
	}
	var tpl map[string]any
	_ = json.Unmarshal(create.Body.Bytes(), &tpl)
	tplID := int64(tpl["id"].(float64))

	// 生成计划
	gen := doJSON(t, r, "POST", fmt.Sprintf("/api/v1/purchase-plan-templates/%d/generate", tplID), nil, purchase)
	if gen.Code != 200 {
		t.Fatalf("generate status=%d body=%s", gen.Code, gen.Body.String())
	}
	var plan map[string]any
	_ = json.Unmarshal(gen.Body.Bytes(), &plan)
	if plan["name"] != "周期模板" || plan["status"] != "正常" {
		t.Fatalf("generated plan=%v", plan)
	}
	// 模板仍在
	detail := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/purchase-plan-templates/%d", tplID), purchase)
	if detail.Code != 200 {
		t.Fatalf("template should remain, status=%d", detail.Code)
	}
}

func TestShareLinkFlow(t *testing.T) {
	r := newTestEngine(t)
	purchase := login(t, r, "purchase")
	id, _ := createPlan(t, r, purchase, "分享物资")
	// 创建分享
	create := doJSON(t, r, "POST", "/api/v1/shares",
		map[string]any{"share_type": "purchase_plan", "item_ids": []any{id}, "expires_in": "24h",
			"columns": []any{"name", "model_spec", "planned_qty"}}, purchase)
	if create.Code != 201 {
		t.Fatalf("create share status=%d body=%s", create.Code, create.Body.String())
	}
	var share map[string]any
	_ = json.Unmarshal(create.Body.Bytes(), &share)
	token := share["token"].(string)
	if share["item_count"] != float64(1) {
		t.Fatalf("item_count=%v", share["item_count"])
	}
	// 匿名读取
	pub := testutil.Do(t, r, "GET", "/api/v1/shares/"+token, nil)
	if pub.Code != 200 {
		t.Fatalf("public share status=%d body=%s", pub.Code, pub.Body.String())
	}
	var pubBody map[string]any
	_ = json.Unmarshal(pub.Body.Bytes(), &pubBody)
	if pubBody["share_type"] != "purchase_plan" {
		t.Fatalf("pub=%v", pubBody)
	}
	items := pubBody["items"].([]any)
	if len(items) != 1 || items[0].(map[string]any)["name"] != "分享物资" {
		t.Fatalf("share items=%v", items)
	}
	// 列表
	list := testutil.Do(t, r, "GET", "/api/v1/shares?page=1&page_size=20", purchase)
	if list.Code != 200 {
		t.Fatalf("share list status=%d", list.Code)
	}
	// 撤回
	revoke := testutil.Do(t, r, "DELETE", "/api/v1/shares/"+token, purchase)
	if revoke.Code != 204 {
		t.Fatalf("revoke status=%d body=%s", revoke.Code, revoke.Body.String())
	}
	// 撤回后匿名读取失败
	pub2 := testutil.Do(t, r, "GET", "/api/v1/shares/"+token, nil)
	if pub2.Code != 400 {
		t.Fatalf("revoked share status=%d", pub2.Code)
	}
}

func TestPurchaseRecordSync(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "purchase")
	id, _ := createPlan(t, r, warehouse, "同步物资")
	doJSON(t, r, "PATCH", fmt.Sprintf("/api/v1/purchase-materials/%d", id),
		map[string]any{"name": "同步物资", "model_spec": "S-1", "unit_name": "个", "planned_qty": "5",
			"usage": "同步测试", "material_code": "M-SYNC", "urgency": "正常",
			"demand_department": "HXNI 检修维护部", "actual_demand_person": "张三",
			"purchase_responsible": "李四", "image_ids": []any{}, "version": 1}, warehouse)
	move := doJSON(t, r, "POST", "/api/v1/purchase-materials/batch-move-to-record",
		map[string]any{"materials": []any{map[string]any{"id": id, "version": 2}}}, warehouse)
	var moved []map[string]any
	_ = json.Unmarshal(move.Body.Bytes(), &moved)

	// targets
	targets := testutil.Do(t, r, "GET", "/api/v1/purchase-record-sync/targets?limit=10", warehouse)
	if targets.Code != 200 {
		t.Fatalf("targets status=%d body=%s", targets.Code, targets.Body.String())
	}
}

var _ = gin.Mode
