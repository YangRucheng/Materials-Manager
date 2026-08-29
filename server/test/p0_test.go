package test

import (
	"encoding/json"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

func newTestEngine(t *testing.T) *gin.Engine {
	t.Helper()
	cfg := testutil.NewTestConfig(t)
	db := testutil.OpenTestDB(t, cfg)
	testutil.SeedUsers(t, db)
	return testutil.TestServer(t, cfg, db)
}

func TestHealth(t *testing.T) {
	r := newTestEngine(t)
	w := testutil.Do(t, r, "GET", "/health", nil)
	if w.Code != 200 {
		t.Fatalf("health status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["status"] != "ok" || body["database"] != "ok" {
		t.Fatalf("health body=%s", w.Body.String())
	}
}

func TestVersion(t *testing.T) {
	r := newTestEngine(t)
	w := testutil.Do(t, r, "GET", "/api/v1/version", nil)
	if w.Code != 200 {
		t.Fatalf("version status=%d", w.Code)
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["app_name"] != "电气车间备件管理系统" || body["version"] != "1.0.0" {
		t.Fatalf("version body=%s", w.Body.String())
	}
	// commit/build_time 未配置时为 null
	if v, ok := body["commit"]; !ok || v != nil {
		t.Fatalf("commit 应为 null: %v", body["commit"])
	}
}

func TestOpenAPIJSON(t *testing.T) {
	r := newTestEngine(t)
	w := testutil.Do(t, r, "GET", "/api/v1/openapi.json", nil)
	if w.Code != 200 {
		t.Fatalf("openapi status=%d", w.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["openapi"] != "3.1.0" {
		t.Fatalf("openapi version=%v", body["openapi"])
	}
	paths, ok := body["paths"].(map[string]any)
	if !ok || len(paths) == 0 {
		t.Fatal("openapi paths 缺失")
	}
	if _, ok := paths["/api/v1/auth/login"]; !ok {
		t.Fatal("openapi 缺少 /api/v1/auth/login")
	}
}

func TestRouteNotFound(t *testing.T) {
	r := newTestEngine(t)
	w := testutil.Do(t, r, "GET", "/api/v1/does-not-exist", nil)
	if w.Code != 400 {
		t.Fatalf("ROUTE_NOT_FOUND 状态码=%d (约定禁用 404)", w.Code)
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["code"] != "ROUTE_NOT_FOUND" || body["message"] != "接口路径不存在" {
		t.Fatalf("body=%s", w.Body.String())
	}
	if _, ok := body["request_id"]; !ok {
		t.Fatal("错误体缺少 request_id")
	}
}

func TestRequestIDHeader(t *testing.T) {
	r := newTestEngine(t)
	w := testutil.Do(t, r, "GET", "/health", map[string]string{"X-Request-ID": "req-123"})
	if got := w.Header().Get("X-Request-ID"); got != "req-123" {
		t.Fatalf("X-Request-ID 未回显: %q", got)
	}
	if w.Header().Get("X-Response-Time") == "" {
		t.Fatal("缺少 X-Response-Time 头")
	}
}

func TestCORSPreflight(t *testing.T) {
	cfg := testutil.NewTestConfig(t)
	db := testutil.OpenTestDB(t, cfg)
	r := testutil.TestServer(t, cfg, db)
	w := testutil.Do(t, r, "OPTIONS", "/api/v1/version",
		map[string]string{
			"Origin":                         "https://spares.example.com",
			"Access-Control-Request-Method":  "GET",
			"Access-Control-Request-Headers": "Content-Type",
		})
	if w.Code != 200 {
		t.Fatalf("预检状态=%d", w.Code)
	}
	if got := w.Header().Get("Access-Control-Allow-Origin"); got != "https://spares.example.com" {
		t.Fatalf("Allow-Origin=%q", got)
	}
	if got := w.Header().Get("Access-Control-Allow-Headers"); got != "Content-Type" {
		t.Fatalf("Allow-Headers=%q", got)
	}
	if w.Header().Get("Access-Control-Allow-Methods") == "" {
		t.Fatal("缺少 Allow-Methods")
	}
}

func TestCORSRefererOrigin(t *testing.T) {
	cfg := testutil.NewTestConfig(t)
	cfg.CORSOrigins = []string{"https://app.example.com", ".example.com"}
	db := testutil.OpenTestDB(t, cfg)
	r := testutil.TestServer(t, cfg, db)
	// Referer 优先
	w := testutil.Do(t, r, "GET", "/health",
		map[string]string{
			"Referer": "https://spares.example.com/login?x=1",
			"Origin":  "https://spares.example.com",
		})
	if got := w.Header().Get("Access-Control-Allow-Origin"); got != "https://spares.example.com" {
		t.Fatalf("子域匹配失败: %q", got)
	}
	// 非白名单来源不回显
	w2 := testutil.Do(t, r, "GET", "/health",
		map[string]string{"Origin": "https://evil.example.net"})
	if got := w2.Header().Get("Access-Control-Allow-Origin"); got != "" {
		t.Fatalf("非白名单不应回显: %q", got)
	}
}
