package test

import (
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

// createStock 创建二级库物资，返回 id。
func createStock(t *testing.T, r *gin.Engine, headers map[string]string, name string) int64 {
	t.Helper()
	if name == "" {
		name = "交流接触器"
	}
	w := doJSON(t, r, "POST", "/api/v1/stock-materials",
		map[string]any{"name": name, "model_spec": "CJX2-2510 220V", "unit_name": "个", "remark": "测试", "image_ids": []any{}}, headers)
	if w.Code != 201 {
		t.Fatalf("create stock status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	return int64(body["id"].(float64))
}

func operationPayload(requestID string, materialID int64, quantity string, occurredAt string) map[string]any {
	return map[string]any{
		"client_request_id": requestID,
		"occurred_at":       occurredAt,
		"source_type":       "MANUAL",
		"business_reason":   "测试库存业务",
		"lines":             []any{map[string]any{"stock_material_id": materialID, "quantity": quantity}},
	}
}

func TestCreateStockMaterial(t *testing.T) {
	r := newTestEngine(t)
	admin := login(t, r, "admin")
	w := doJSON(t, r, "POST", "/api/v1/stock-materials",
		map[string]any{"name": "断路器", "model_spec": "DZ47-63 C16", "unit_name": "个", "remark": "", "image_ids": []any{}}, admin)
	if w.Code != 201 {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["current_qty"] != "0" {
		t.Fatalf("current_qty=%v", body["current_qty"])
	}
	if body["replenishment_policy"] != nil {
		t.Fatalf("replenishment_policy 应为 null: %v", body["replenishment_policy"])
	}
	if body["has_operation_records"] != false {
		t.Fatalf("has_operation_records=%v", body["has_operation_records"])
	}
	if _, ok := body["uuid"]; !ok || body["uuid"] == "" {
		t.Fatalf("uuid 缺失: %v", body["uuid"])
	}
	// 相同 identity -> 409
	dup := doJSON(t, r, "POST", "/api/v1/stock-materials",
		map[string]any{"name": "断路器", "model_spec": "DZ47-63 C16", "unit_name": "个", "remark": "", "image_ids": []any{}}, admin)
	if dup.Code != 409 {
		t.Fatalf("duplicate status=%d body=%s", dup.Code, dup.Body.String())
	}
	var dupBody map[string]any
	_ = json.Unmarshal(dup.Body.Bytes(), &dupBody)
	if dupBody["code"] != "DUPLICATE_MATERIAL" {
		t.Fatalf("code=%v", dupBody["code"])
	}
}

func TestInboundOutboundSemantics(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	materialID := createStock(t, r, warehouse, "业务原因测试")

	// 入库可不填原因（不传 business_reason 字段）
	inboundPayload := map[string]any{
		"client_request_id": "inbound-without-reason",
		"occurred_at":       "2026-07-18T10:00:00+08:00",
		"source_type":       "MANUAL",
		"lines":             []any{map[string]any{"stock_material_id": materialID, "quantity": "1"}},
	}
	inbound := doJSON(t, r, "POST", "/api/v1/inventory/inbounds", inboundPayload, warehouse)
	if inbound.Code != 201 {
		t.Fatalf("inbound status=%d body=%s", inbound.Code, inbound.Body.String())
	}
	var inBody map[string]any
	_ = json.Unmarshal(inbound.Body.Bytes(), &inBody)
	if inBody["business_reason"] != "" {
		t.Fatalf("入库原因应为空: %v", inBody["business_reason"])
	}

	// 出库必须填原因（不传 business_reason）
	noReasonPayload := map[string]any{
		"client_request_id": "outbound-no-reason",
		"occurred_at":       "2026-07-18T11:00:00+08:00",
		"source_type":       "MANUAL",
		"lines":             []any{map[string]any{"stock_material_id": materialID, "quantity": "1"}},
	}
	outbound := doJSON(t, r, "POST", "/api/v1/inventory/outbounds", noReasonPayload, warehouse)
	if outbound.Code != 400 {
		t.Fatalf("outbound no reason status=%d", outbound.Code)
	}
	checkCode(t, outbound, "BUSINESS_REASON_REQUIRED", "出库必须填写用途")

	payload := operationPayload("outbound-no-receiver", materialID, "1", "2026-07-18T11:00:00+08:00")
	payload["business_reason"] = "测试出库"
	noReceiver := doJSON(t, r, "POST", "/api/v1/inventory/outbounds", payload, warehouse)
	if noReceiver.Code != 400 {
		t.Fatalf("no receiver status=%d body=%s", noReceiver.Code, noReceiver.Body.String())
	}
	checkCode(t, noReceiver, "RECEIVER_REQUIRED", "出库必须填写领用人")

	payload["receiver_name"] = "测试领用人"
	ok := doJSON(t, r, "POST", "/api/v1/inventory/outbounds", payload, warehouse)
	if ok.Code != 201 {
		t.Fatalf("outbound status=%d body=%s", ok.Code, ok.Body.String())
	}
	var outBody map[string]any
	_ = json.Unmarshal(ok.Body.Bytes(), &outBody)
	if outBody["receiver_unit"] != nil || outBody["subitem_no"] != nil {
		t.Fatalf("receiver_unit/subitem_no 应为 null: %v", outBody)
	}
	if outBody["operation_no"].(string)[:3] != "OUT" {
		t.Fatalf("operation_no=%v", outBody["operation_no"])
	}
}

func checkCode(t *testing.T, w *httptest.ResponseRecorder, wantCode, wantMsg string) {
	t.Helper()
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["code"] != wantCode {
		t.Fatalf("code=%v want=%s body=%s", body["code"], wantCode, w.Body.String())
	}
	if body["message"] != wantMsg {
		t.Fatalf("message=%v want=%s", body["message"], wantMsg)
	}
}

func checkCodeMsg(t *testing.T, w *httptest.ResponseRecorder, wantCode string) {
	t.Helper()
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["code"] != wantCode {
		t.Fatalf("code=%v want=%s body=%s", body["code"], wantCode, w.Body.String())
	}
}

func TestBalanceReplay(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	materialID := createStock(t, r, warehouse, "重放测试")

	// 入 10
	in := doJSON(t, r, "POST", "/api/v1/inventory/inbounds",
		operationPayload("replay-in-1", materialID, "10", "2026-07-18T10:00:00+08:00"), warehouse)
	if in.Code != 201 {
		t.Fatalf("in status=%d", in.Code)
	}
	// 出 3
	out := doJSON(t, r, "POST", "/api/v1/inventory/outbounds",
		withReceiver(operationPayload("replay-out-1", materialID, "3", "2026-07-18T11:00:00+08:00")), warehouse)
	if out.Code != 201 {
		t.Fatalf("out status=%d body=%s", out.Code, out.Body.String())
	}
	// 入 2
	in2 := doJSON(t, r, "POST", "/api/v1/inventory/inbounds",
		operationPayload("replay-in-2", materialID, "2", "2026-07-18T12:00:00+08:00"), warehouse)
	if in2.Code != 201 {
		t.Fatalf("in2 status=%d", in2.Code)
	}

	// 余额应为 10-3+2=9
	detail := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/inventory/balances/%d", materialID), warehouse)
	if detail.Code != 200 {
		t.Fatalf("balance detail status=%d", detail.Code)
	}
	var balance map[string]any
	_ = json.Unmarshal(detail.Body.Bytes(), &balance)
	if balance["current_qty"] != "9" {
		t.Fatalf("current_qty=%v", balance["current_qty"])
	}

	// 第一条入库行的 before/after
	opDetail := testutil.Do(t, r, "GET", "/api/v1/inventory/operations/1", warehouse)
	var op map[string]any
	_ = json.Unmarshal(opDetail.Body.Bytes(), &op)
	lines := op["lines"].([]any)
	line0 := lines[0].(map[string]any)
	if line0["before_qty"] != "0" || line0["after_qty"] != "10" {
		t.Fatalf("第一条流水 before/after 错误: %v", line0)
	}
	// 第二条出库行 before=10 after=7
	opDetail2 := testutil.Do(t, r, "GET", "/api/v1/inventory/operations/2", warehouse)
	var op2 map[string]any
	_ = json.Unmarshal(opDetail2.Body.Bytes(), &op2)
	line1 := op2["lines"].([]any)[0].(map[string]any)
	if line1["before_qty"] != "10" || line1["after_qty"] != "7" {
		t.Fatalf("第二条流水 before/after 错误: %v", line1)
	}
}

func withReceiver(payload map[string]any) map[string]any {
	payload["receiver_name"] = "测试领用人"
	return payload
}

func TestOperationIdempotency(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	materialID := createStock(t, r, warehouse, "幂等测试")
	payload := operationPayload("idempotent-1", materialID, "5", "2026-07-18T10:00:00+08:00")
	first := doJSON(t, r, "POST", "/api/v1/inventory/inbounds", payload, warehouse)
	if first.Code != 201 {
		t.Fatalf("first status=%d", first.Code)
	}
	second := doJSON(t, r, "POST", "/api/v1/inventory/inbounds", payload, warehouse)
	if second.Code != 201 {
		t.Fatalf("second status=%d", second.Code)
	}
	var a, b map[string]any
	_ = json.Unmarshal(first.Body.Bytes(), &a)
	_ = json.Unmarshal(second.Body.Bytes(), &b)
	if a["id"] != b["id"] || a["operation_no"] != b["operation_no"] {
		t.Fatalf("幂等应返回同一流水: %v vs %v", a["id"], b["id"])
	}
	// 余额只入一次 -> 5
	detail := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/inventory/balances/%d", materialID), warehouse)
	var balance map[string]any
	_ = json.Unmarshal(detail.Body.Bytes(), &balance)
	if balance["current_qty"] != "5" {
		t.Fatalf("幂等后余额=%v", balance["current_qty"])
	}
}

func TestReverseOperation(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	materialID := createStock(t, r, warehouse, "冲销测试")
	// 入 8
	doJSON(t, r, "POST", "/api/v1/inventory/inbounds",
		operationPayload("rev-in-1", materialID, "8", "2026-07-18T10:00:00+08:00"), warehouse)
	// 出 3
	out := doJSON(t, r, "POST", "/api/v1/inventory/outbounds",
		withReceiver(operationPayload("rev-out-1", materialID, "3", "2026-07-18T11:00:00+08:00")), warehouse)
	var outBody map[string]any
	_ = json.Unmarshal(out.Body.Bytes(), &outBody)
	opID := int64(outBody["id"].(float64))

	// 冲销出库（反向入库 3）
	reverse := doJSON(t, r, "POST", fmt.Sprintf("/api/v1/inventory/operations/%d/reverse", opID),
		map[string]any{"client_request_id": "rev-rev-1", "reason": "操作有误",
			"lines": []any{map[string]any{"stock_material_id": materialID, "quantity": "3"}}}, warehouse)
	if reverse.Code != 200 {
		t.Fatalf("reverse status=%d body=%s", reverse.Code, reverse.Body.String())
	}
	var revBody map[string]any
	_ = json.Unmarshal(reverse.Body.Bytes(), &revBody)
	if revBody["operation_type"] != "INBOUND" || revBody["source_type"] != "REVERSAL" {
		t.Fatalf("冲销方向/来源错误: %v", revBody)
	}
	if revBody["is_reversed"] != true {
		t.Fatalf("冲销自身 is_reversed 应为 true（reversal_of_id 指向原流水）")
	}
	if len(revBody["lines"].([]any)) != 1 {
		t.Fatalf("冲销应包含 1 行: %v", revBody["lines"])
	}
	// 原流水 is_reversed = false（它本身不是冲销流水）
	orig := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/inventory/operations/%d", opID), warehouse)
	var origBody map[string]any
	_ = json.Unmarshal(orig.Body.Bytes(), &origBody)
	if origBody["is_reversed"] != false {
		t.Fatalf("原流水 is_reversed 应为 false: %v", origBody["is_reversed"])
	}
	// 原流水可冲余量归零
	origLines := origBody["lines"].([]any)
	if origLines[0].(map[string]any)["remaining_qty"] != "0" {
		t.Fatalf("原流水 remaining_qty 应为 0: %v", origLines[0])
	}
	// 余额回到 8
	detail := testutil.Do(t, r, "GET", fmt.Sprintf("/api/v1/inventory/balances/%d", materialID), warehouse)
	var balance map[string]any
	_ = json.Unmarshal(detail.Body.Bytes(), &balance)
	if balance["current_qty"] != "8" {
		t.Fatalf("冲销后余额=%v", balance["current_qty"])
	}
	// 超量冲销 -> 409
	over := doJSON(t, r, "POST", fmt.Sprintf("/api/v1/inventory/operations/%d/reverse", opID),
		map[string]any{"client_request_id": "rev-over", "reason": "x",
			"lines": []any{map[string]any{"stock_material_id": materialID, "quantity": "99"}}}, warehouse)
	if over.Code != 409 {
		t.Fatalf("超量冲销 status=%d body=%s", over.Code, over.Body.String())
	}
	checkCodeMsg(t, over, "INSUFFICIENT_QUANTITY")
}

func TestQuantityPrecisionValidation(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	materialID := createStock(t, r, warehouse, "精度测试")
	bad := doJSON(t, r, "POST", "/api/v1/inventory/inbounds",
		operationPayload("precision-bad", materialID, "1.25", "2026-07-18T10:00:00+08:00"), warehouse)
	if bad.Code != 400 {
		t.Fatalf("precision status=%d body=%s", bad.Code, bad.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(bad.Body.Bytes(), &body)
	if body["code"] != "INVALID_QUANTITY_PRECISION" {
		t.Fatalf("code=%v", body["code"])
	}
	// 尾零可接受
	ok := doJSON(t, r, "POST", "/api/v1/inventory/inbounds",
		operationPayload("precision-ok", materialID, "1.50", "2026-07-18T10:00:00+08:00"), warehouse)
	if ok.Code != 201 {
		t.Fatalf("precision ok status=%d body=%s", ok.Code, ok.Body.String())
	}
}

func TestReplenishmentPolicyAndLowStock(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	materialID := createStock(t, r, warehouse, "补库测试")
	// 入库 2
	doJSON(t, r, "POST", "/api/v1/inventory/inbounds",
		operationPayload("policy-in", materialID, "2", "2026-07-18T10:00:00+08:00"), warehouse)
	// 设安全库存 5
	policy := doJSON(t, r, "PUT", fmt.Sprintf("/api/v1/stock-materials/%d/replenishment-policy", materialID),
		map[string]any{"minimum_qty": "5", "enabled": true, "version": 0}, warehouse)
	if policy.Code != 200 {
		t.Fatalf("policy status=%d body=%s", policy.Code, policy.Body.String())
	}
	var policyBody map[string]any
	_ = json.Unmarshal(policy.Body.Bytes(), &policyBody)
	pol := policyBody["replenishment_policy"].(map[string]any)
	if pol["minimum_qty"] != "5" || pol["enabled"] != true {
		t.Fatalf("policy=%v", pol)
	}
	// low-stock 列表包含该物资
	low := testutil.Do(t, r, "GET", "/api/v1/inventory/low-stock?page=1&page_size=20", warehouse)
	var lowPage map[string]any
	_ = json.Unmarshal(low.Body.Bytes(), &lowPage)
	if int(lowPage["total"].(float64)) != 1 {
		t.Fatalf("low-stock total=%v body=%s", lowPage["total"], low.Body.String())
	}
	// 一键补库草稿
	draft := doJSON(t, r, "POST", fmt.Sprintf("/api/v1/inventory/low-stock/%d/create-replenishment-draft", materialID),
		map[string]any{"demand_date": "2026-07-18", "actual_demand_person": "张三", "purchase_responsible": "李四", "planned_qty": "10"}, warehouse)
	if draft.Code != 200 {
		t.Fatalf("draft status=%d body=%s", draft.Code, draft.Body.String())
	}
	var draftBody map[string]any
	_ = json.Unmarshal(draft.Body.Bytes(), &draftBody)
	if draftBody["next"] != "purchase_material" || draftBody["resource_id"] == nil {
		t.Fatalf("draft body=%s", draft.Body.String())
	}
}

func TestDashboardSummary(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	createStock(t, r, warehouse, "统计物资1")
	createStock(t, r, warehouse, "统计物资2")
	w := testutil.Do(t, r, "GET", "/api/v1/dashboard/summary", warehouse)
	if w.Code != 200 {
		t.Fatalf("summary status=%d", w.Code)
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if int(body["stock_material_count"].(float64)) != 2 {
		t.Fatalf("stock_material_count=%v", body["stock_material_count"])
	}
	if int(body["low_stock_count"].(float64)) != 0 {
		t.Fatalf("low_stock_count=%v", body["low_stock_count"])
	}
}

func TestInventoryPermissions(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	readonly := login(t, r, "readonly")
	materialID := createStock(t, r, warehouse, "权限测试物资")
	// readonly 可以读，但不能写
	w := doJSON(t, r, "POST", "/api/v1/inventory/inbounds",
		operationPayload("perm-in", materialID, "1", "2026-07-18T10:00:00+08:00"), readonly)
	if w.Code != 403 {
		t.Fatalf("readonly 入库应 403, status=%d", w.Code)
	}
	// readonly 不能建物资
	w2 := doJSON(t, r, "POST", "/api/v1/stock-materials",
		map[string]any{"name": "x", "model_spec": "y", "unit_name": "个", "image_ids": []any{}}, readonly)
	if w2.Code != 403 {
		t.Fatalf("readonly 建物资应 403, status=%d", w2.Code)
	}
}

func TestDeleteMaterialWithOperationsBlocked(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	materialID := createStock(t, r, warehouse, "删除测试")
	doJSON(t, r, "POST", "/api/v1/inventory/inbounds",
		operationPayload("del-in", materialID, "1", "2026-07-18T10:00:00+08:00"), warehouse)
	w := testutil.Do(t, r, "DELETE", fmt.Sprintf("/api/v1/stock-materials/%d", materialID),
		map[string]string{"Authorization": warehouse["Authorization"], "If-Match": "1"})
	if w.Code != 409 {
		t.Fatalf("有流水应 409, status=%d body=%s", w.Code, w.Body.String())
	}
}
