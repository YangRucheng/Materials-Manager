package test

import (
	"net/http/httptest"
	"testing"

	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

// TestSweepLocalSanity 用本地 SQLite 测试服务器验证逐接口扫描逻辑可运行。
func TestSweepLocalSanity(t *testing.T) {
	cfg := testutil.NewTestConfig(t)
	db := testutil.OpenTestDB(t, cfg)
	testutil.SeedUsers(t, db)
	r := testutil.TestServer(t, cfg, db)
	ts := httptest.NewServer(r)
	defer ts.Close()
	runSweep(t, ts.URL)
}
