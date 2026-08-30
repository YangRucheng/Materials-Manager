package testutil

import (
	"testing"
)

func TestAdminDSN(t *testing.T) {
	dsn, err := adminDSN("mysql+asyncmy://root:root@127.0.0.1:3306/spare_parts?charset=utf8mb4")
	if err != nil {
		t.Fatal(err)
	}
	want := "root:root@tcp(127.0.0.1:3306)/?parseTime=true&loc=UTC&multiStatements=true&charset=utf8mb4"
	if dsn != want {
		t.Fatalf("adminDSN = %q, want %q", dsn, want)
	}
	if _, err := adminDSN("sqlite+aiosqlite:///:memory:"); err == nil {
		t.Fatal("非 MySQL URL 应报错")
	}
}

func TestBuildTestDSN(t *testing.T) {
	dsn := buildTestDSN("mysql+asyncmy://root:root@127.0.0.1:3306/spare_parts?charset=utf8mb4", "spare_parts_test_abc")
	want := "root:root@tcp(127.0.0.1:3306)/spare_parts_test_abc?parseTime=true&loc=UTC&charset=utf8mb4"
	if dsn != want {
		t.Fatalf("buildTestDSN = %q, want %q", dsn, want)
	}
}
