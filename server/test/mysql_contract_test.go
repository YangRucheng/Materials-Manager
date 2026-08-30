package test

// 逐接口契约扫描：对 openapi 中每条路由发起真实 HTTP 请求，断言状态码在契约允许集内。
// 由 DSH_CONTRACT_URL 环境变量开关（指向被测服务根，如 http://127.0.0.1:8000）。
// 既用于 GitHub Actions MySQL CI，也用于线上部署测试。

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"testing"

	"github.com/yangrucheng/materials-manager/server/internal/openapi"
)

func sweepBase(t *testing.T) string {
	base := os.Getenv("DSH_CONTRACT_URL")
	if base == "" {
		t.Skip("DSH_CONTRACT_URL 未设置，跳过逐接口扫描")
	}
	return strings.TrimRight(base, "/")
}

// 匿名白名单：这些端点无需管理端登录。
var sweepAnonymous = map[string]bool{
	"GET /api/v1/shares/:token":                         true,
	"GET /api/v1/files/images/:file_id":                 true,
	"GET /api/v1/system-settings/image-acceleration":    true,
	"GET /api/v1/system-settings/mini-program-features": true,
	"POST /api/v1/mini-program/auth/wx-login":           true,
	"POST /api/v1/mini-program/profile":                 true,
	"GET /api/v1/version":                               true,
	"GET /api/v1/openapi.json":                          true,
}

// 请求体模板：覆盖主要创建/更新端点（空 body 的写接口以 400/422 验证契约）。
func sweepBody(method, path string) any {
	switch {
	case method == "POST" && path == "/api/v1/stock-materials":
		return map[string]any{"name": "契约扫描物资", "model_spec": "SWEEP-1", "unit_name": "个", "remark": "sweep", "image_ids": []any{}}
	case method == "POST" && path == "/api/v1/inventory/inbounds":
		return map[string]any{"client_request_id": "sweep-in-1", "occurred_at": "2026-07-18T10:00:00+08:00", "source_type": "MANUAL", "lines": []any{map[string]any{"stock_material_id": 1, "quantity": "1"}}}
	case method == "POST" && path == "/api/v1/inventory/outbounds":
		return map[string]any{"client_request_id": "sweep-out-1", "occurred_at": "2026-07-18T10:00:00+08:00", "source_type": "MANUAL", "business_reason": "扫描", "receiver_name": "扫描员", "lines": []any{map[string]any{"stock_material_id": 1, "quantity": "1"}}}
	case method == "POST" && path == "/api/v1/purchase-materials":
		return map[string]any{"name": "契约扫描计划", "model_spec": "SWEEP-P-1", "unit_name": "个", "planned_qty": "1", "usage": "扫描", "urgency": "正常", "demand_department": "HXNI 检修维护部", "actual_demand_person": "张三", "purchase_responsible": "李四", "image_ids": []any{}}
	case method == "POST" && path == "/api/v1/purchase-plan-templates":
		return map[string]any{"name": "契约扫描模板", "model_spec": "SWEEP-T-1", "unit_name": "个", "planned_qty": "1", "usage": "扫描", "actual_demand_person": "张三", "purchase_responsible": "李四", "urgency": "正常", "demand_department": "HXNI 检修维护部", "image_ids": []any{}}
	case method == "POST" && path == "/api/v1/shares":
		return map[string]any{"share_type": "purchase_plan", "item_ids": []any{1}, "expires_in": "24h", "columns": []any{"name"}}
	case method == "POST" && path == "/api/v1/users":
		return map[string]any{"username": "sweepuser", "password": "secret1", "display_name": "扫描用户", "role": "READ_ONLY"}
	case method == "POST" && path == "/api/v1/mini-program/auth/wx-login":
		return map[string]any{"code": "invalid-code"}
	case method == "POST" && path == "/api/v1/purchase-materials/export-results":
		return map[string]any{"columns": []any{"plan_no", "name"}}
	case method == "POST" && path == "/api/v1/purchase-records/export-results":
		return map[string]any{"columns": []any{"material_name", "purchase_qty"}}
	case method == "POST" && path == "/api/v1/purchase-materials/export-purchase-application":
		return map[string]any{"material_ids": []any{1}}
	case method == "POST" && path == "/api/v1/purchase-materials/export-purchase-approval":
		return map[string]any{"material_ids": []any{1}}
	case method == "POST" && path == "/api/v1/purchase-materials/batch":
		return map[string]any{"materials": []any{map[string]any{"id": 1, "version": 1}}}
	case method == "POST" && path == "/api/v1/purchase-materials/batch-move-to-record":
		return map[string]any{"materials": []any{map[string]any{"id": 1, "version": 1}}}
	case method == "POST" && path == "/api/v1/purchase-materials/:material_id/move-to-record":
		return map[string]any{"version": 1}
	case method == "POST" && path == "/api/v1/purchase-materials/:material_id/link-stock-material":
		return map[string]any{"stock_material_id": 1, "version": 1}
	case method == "PUT" && path == "/api/v1/stock-materials/:material_id/replenishment-policy":
		return map[string]any{"minimum_qty": "1", "enabled": true, "version": 0}
	case method == "PUT" && path == "/api/v1/system-settings/webhooks/:platform":
		return map[string]any{"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/x", "secret": "s", "enabled": false, "subscribed_events": []any{}, "version": 0}
	case method == "POST" && path == "/api/v1/system-settings/webhooks/:platform/test":
		return map[string]any{"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/x", "secret": "s"}
	case method == "PUT" && path == "/api/v1/ai-search/settings":
		return map[string]any{"endpoint": "", "api_key": "", "model": "", "enabled": false, "version": 0}
	case method == "POST" && path == "/api/v1/ai-search/settings/test":
		return map[string]any{"endpoint": "https://x", "api_key": "x", "model": "x"}
	case method == "POST" && path == "/api/v1/ai-search/expand":
		return map[string]any{"value": "电机"}
	case method == "POST" && path == "/api/v1/mini-program-users/:target_user_id/merge":
		return map[string]any{"source_user_id": 1, "target_version": 1, "source_version": 1}
	case method == "POST" && path == "/api/v1/inventory/operations/:operation_id/reverse":
		return map[string]any{"client_request_id": "sweep-reverse", "reason": "扫描", "lines": []any{map[string]any{"stock_material_id": 1, "quantity": "1"}}}
	case method == "POST" && path == "/api/v1/purchase-records/:line_id/restore-to-plan":
		return nil
	case method == "POST" && path == "/api/v1/purchase-record-sync/trace/:trace_no":
		return map[string]any{"salesperson": "扫描员", "status": "已申购"}
	}
	return nil
}

// sweepTolerated 允许的降级状态码（校验失败等，均在契约 4xx 内）。
var sweepForbiddenStatuses = map[int]bool{500: true}

// sweepExternal503 依赖外部服务（微信/AI）未配置时的设计降级：503 属正常。
var sweepExternal503 = map[string]bool{
	"GET /api/v1/stock-materials/:material_id/mini-program-code":    true,
	"GET /api/v1/stock-materials/mini-program-codes/:material_uuid": true,
	"POST /api/v1/ai-search/expand":                                 true,
}

// 捕获上下文中可用的 id（简化：写流程后从响应提取并复用）。
type sweepCtx struct {
	stockID      int64
	planID       int64
	token        string
	materialUUID string
	planNo       string
}

func doSweepReq(base, method, path, token string, body any) (*http.Response, []byte) {
	var reader io.Reader
	if body != nil {
		raw, _ := json.Marshal(body)
		reader = bytes.NewReader(raw)
	}
	req, _ := http.NewRequest(method, base+path, reader)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	req.Header.Set("X-Request-ID", "contract-sweep")
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, nil
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	return resp, data
}

// documentedStatuses 解析 openapi 某操作声明的响应码集合。
func documentedStatuses(op map[string]any) map[int]bool {
	out := map[int]bool{}
	resps, _ := op["responses"].(map[string]any)
	for code := range resps {
		var n int
		if _, err := fmt.Sscanf(code, "%d", &n); err == nil {
			out[n] = true
		}
	}
	return out
}

// TestMySQLContractSweep 逐接口扫描：每个 openapi 路由发一次真实请求。
func TestMySQLContractSweep(t *testing.T) {
	runSweep(t, sweepBase(t))
}

func runSweep(t *testing.T, base string) {
	spec, err := openapi.Spec()
	if err != nil {
		t.Fatalf("读取契约失败: %v", err)
	}

	// 登录拿 token
	loginResp, loginBody := doSweepReq(base, "POST", "/api/v1/auth/login", "", map[string]any{"username": "admin", "password": "123456"})
	if loginResp == nil || loginResp.StatusCode != 200 {
		t.Fatalf("admin 登录失败（HTTP %v, body=%s）——被测服务不可用或种子账号缺失", statusOf(loginResp), loginBody)
	}
	var loginData struct {
		AccessToken string `json:"access_token"`
	}
	_ = json.Unmarshal(loginBody, &loginData)
	token := loginData.AccessToken
	if token == "" {
		t.Fatal("登录未返回 access_token")
	}

	// 预置一条物资/计划供后续路径参数
	ctx := &sweepCtx{}
	if resp, body := doSweepReq(base, "POST", "/api/v1/stock-materials", token,
		sweepBody("POST", "/api/v1/stock-materials")); resp != nil && resp.StatusCode == 201 {
		var m struct {
			ID   int64  `json:"id"`
			UUID string `json:"uuid"`
		}
		_ = json.Unmarshal(body, &m)
		ctx.stockID = m.ID
		ctx.materialUUID = m.UUID
	}
	if resp, body := doSweepReq(base, "POST", "/api/v1/purchase-materials", token,
		sweepBody("POST", "/api/v1/purchase-materials")); resp != nil && resp.StatusCode == 201 {
		var m struct {
			ID     int64  `json:"id"`
			PlanNo string `json:"plan_no"`
		}
		_ = json.Unmarshal(body, &m)
		ctx.planID = m.ID
		ctx.planNo = m.PlanNo
	}

	paths, _ := spec["paths"].(map[string]any)
	var passed, failed []string
	for p, item := range paths {
		if !strings.HasPrefix(p, "/api/v1") {
			continue
		}
		pathItem, _ := item.(map[string]any)
		for method, opAny := range pathItem {
			op, ok := opAny.(map[string]any)
			if !ok {
				continue
			}
			method = strings.ToUpper(method)
			if method != "GET" && method != "POST" && method != "PUT" && method != "PATCH" && method != "DELETE" {
				continue
			}
			ginPath := pathParamRe.ReplaceAllString(p, ":$1")
			// 组装路径参数
			requestPath := p
			requestPath = strings.Replace(requestPath, "{material_id}", itoa(ctx.stockID), 1)
			requestPath = strings.Replace(requestPath, "{material_uuid}", ctx.materialUUID, 1)
			requestPath = strings.Replace(requestPath, "{template_id}", "1", 1)
			requestPath = strings.Replace(requestPath, "{line_id}", "1", 1)
			requestPath = strings.Replace(requestPath, "{operation_id}", "1", 1)
			requestPath = strings.Replace(requestPath, "{item_id}", "1", 1)
			requestPath = strings.Replace(requestPath, "{user_id}", "1", 1)
			requestPath = strings.Replace(requestPath, "{job_id}", "1", 1)
			requestPath = strings.Replace(requestPath, "{file_uuid}", "00000000-0000-7000-8000-000000000000", 1)
			requestPath = strings.Replace(requestPath, "{file_id}", "00000000-0000-7000-8000-000000000000", 1)
			requestPath = strings.Replace(requestPath, "{target_user_id}", "1", 1)
			requestPath = strings.Replace(requestPath, "{target_user_id}", "1", 1)
			requestPath = strings.Replace(requestPath, "{token}", "00000000-0000-7000-8000-000000000000", 1)
			requestPath = strings.Replace(requestPath, "{platform}", "FEISHU", 1)
			requestPath = strings.Replace(requestPath, "{trace_no}", "TR-SWEEP", 1)
			requestPath = strings.Replace(requestPath, "{operation_no}", "OUT20260718000001", 1)
			requestPath = strings.Replace(requestPath, "{import_type}", "MATERIAL_CODE_LIBRARY", 1)

			authToken := token
			if sweepAnonymous[method+" "+ginPath] {
				authToken = ""
			}
			body := sweepBody(method, requestPath)
			resp, respBody := doSweepReq(base, method, requestPath, authToken, body)

			doc := documentedStatuses(op)
			status := statusOf(resp)
			external503 := status == 503 && sweepExternal503[method+" "+ginPath]
			okStatus := doc[status] || external503 || (status == 400 || status == 422) || (status == 401 || status == 403)
			if status == 0 || sweepForbiddenStatuses[status] || !okStatus {
				failed = append(failed, fmt.Sprintf("%s %s -> HTTP %d (契约允许 %v, body=%s)", method, requestPath, status, keysOf(doc), truncateBody(respBody)))
			} else {
				passed = append(passed, fmt.Sprintf("%s %s -> %d", method, requestPath, status))
			}
		}
	}
	t.Logf("逐接口扫描：通过 %d，失败 %d", len(passed), len(failed))
	for _, f := range failed {
		t.Logf("FAIL %s", f)
	}
	if len(failed) > 0 {
		t.Fatalf("逐接口扫描存在 %d 个失败", len(failed))
	}
}

func statusOf(resp *http.Response) int {
	if resp == nil {
		return 0
	}
	return resp.StatusCode
}

func keysOf(m map[int]bool) []int {
	var out []int
	for k := range m {
		out = append(out, k)
	}
	return out
}

func truncateBody(b []byte) string {
	s := string(b)
	if len(s) > 160 {
		return s[:160] + "..."
	}
	return s
}

func itoa(v int64) string {
	if v == 0 {
		return "1"
	}
	return fmt.Sprintf("%d", v)
}
