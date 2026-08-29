package test

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/openapi"
	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

// TestOpenAPIContractDrift 校验内嵌 openapi 与 docs/openapi.yaml 一致。
func TestOpenAPIContractDrift(t *testing.T) {
	repoDoc, err := os.ReadFile(filepath.Join("..", "docs", "openapi.yaml"))
	if err != nil {
		t.Skipf("无法读取 docs/openapi.yaml: %v", err)
	}
	embedded := openapi.YAMLBytes()
	if string(repoDoc) != string(embedded) {
		t.Fatal("server/internal/openapi/openapi.yaml 与 docs/openapi.yaml 不一致，请重新复制")
	}
}

var pathParamRe = regexp.MustCompile(`\{([^}]+)\}`)

func ginPath(openAPIPath string) string {
	return pathParamRe.ReplaceAllString(openAPIPath, ":$1")
}

// OpenAPIRoutes 返回 openapi 中 /api/v1 下的所有 (method, path)。
func OpenAPIRoutes(t *testing.T) map[string]bool {
	t.Helper()
	spec, err := openapi.Spec()
	if err != nil {
		t.Fatal(err)
	}
	paths, _ := spec["paths"].(map[string]any)
	routes := map[string]bool{}
	for p, item := range paths {
		if !strings.HasPrefix(p, "/api/v1") {
			continue
		}
		pathItem, _ := item.(map[string]any)
		for method, op := range pathItem {
			if _, ok := op.(map[string]any); !ok {
				continue
			}
			switch strings.ToUpper(method) {
			case "GET", "POST", "PUT", "PATCH", "DELETE":
				routes[strings.ToUpper(method)+" "+ginPath(p)] = true
			}
		}
	}
	return routes
}

// 排除的端点（P6 导出任务 / P8 AI 扩词 等，见各期 TODO）。
var knownGapRe = []string{
	"/api/v1/ai-search",
	"/api/v1/excel-export-jobs",
	"/api/v1/files/images", // 部分已实现；这里由子测试单独判定
}

func isKnownGap(route string) bool {
	for _, prefix := range knownGapRe {
		if strings.Contains(route, prefix) {
			return true
		}
	}
	return false
}

// TestOpenAPIRouteCoverage 报告 openapi 中尚未注册的路由（最终 P10 应清零）。
func TestOpenAPIRouteCoverage(t *testing.T) {
	cfg := testutil.NewTestConfig(t)
	db := testutil.OpenTestDB(t, cfg)
	r := testutil.TestServer(t, cfg, db)

	registered := map[string]bool{}
	for _, route := range r.Routes() {
		registered[route.Method+" "+route.Path] = true
	}

	expected := OpenAPIRoutes(t)
	var missing []string
	for route := range expected {
		if registered[route] {
			continue
		}
		if isKnownGap(route) {
			continue
		}
		missing = append(missing, route)
	}
	if len(missing) > 0 {
		t.Errorf("openapi 中存在未注册的路由（%d 个）：", len(missing))
		for _, m := range missing {
			t.Errorf("  MISSING %s", m)
		}
	}
	_ = gin.Mode
}
