package serialize_test

import (
	"testing"
	"time"

	"github.com/shopspring/decimal"

	"github.com/yangrucheng/materials-manager/server/internal/serialize"
)

func TestDecimalToString(t *testing.T) {
	cases := map[string]string{
		"12.5":  "12.5",
		"12.0":  "12",
		"12.50": "12.5",
		"0":     "0",
		"0.0":   "0",
		"100":   "100",
		"1.5":   "1.5",
		"0.5":   "0.5",
	}
	for in, want := range cases {
		d, err := decimal.NewFromString(in)
		if err != nil {
			t.Fatal(err)
		}
		if got := serialize.DecimalToString(d); got != want {
			t.Errorf("DecimalToString(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestTimeFormats(t *testing.T) {
	// 注意：Go time.Parse 无法解析 "+00:00" 结尾的 Python isoformat；这里用已构造的 time 验证输出。
	utc := time.Date(2024, 1, 1, 8, 0, 0, 0, time.UTC)
	if got := serialize.FormatUTCZ(utc); got != "2024-01-01T08:00:00Z" {
		t.Errorf("FormatUTCZ zero us = %q", got)
	}
	utcUs := time.Date(2024, 1, 1, 8, 0, 0, 123000000, time.UTC)
	if got := serialize.FormatUTCZ(utcUs); got != "2024-01-01T08:00:00.123000Z" {
		t.Errorf("FormatUTCZ with us = %q", got)
	}
	if got := serialize.FormatOffset(utc); got != "2024-01-01T08:00:00+00:00" {
		t.Errorf("FormatOffset = %q", got)
	}
	if got := serialize.FormatOffset(utcUs); got != "2024-01-01T08:00:00.123000+00:00" {
		t.Errorf("FormatOffset us = %q", got)
	}
	if got := serialize.FormatNaive(utc); got != "2024-01-01T08:00:00" {
		t.Errorf("FormatNaive = %q", got)
	}
	if got := serialize.FormatDate(utc); got != "2024-01-01" {
		t.Errorf("FormatDate = %q", got)
	}
}

func TestParseDateTime(t *testing.T) {
	cases := map[string]string{
		"2026-07-18T10:00:00+08:00":     "2026-07-18T02:00:00Z",
		"2026-07-18T10:00:00Z":          "2026-07-18T10:00:00Z",
		"2026-07-18T10:00:00.123+08:00": "2026-07-18T02:00:00.123000Z",
	}
	for in, want := range cases {
		got, err := serialize.ParseDateTime(in)
		if err != nil {
			t.Fatalf("ParseDateTime(%q) err: %v", in, err)
		}
		if serialize.FormatUTCZ(got) != want {
			t.Errorf("ParseDateTime(%q) = %v, want %s", in, got.UTC(), want)
		}
	}
	if _, err := serialize.ParseDateTime("not-a-date"); err == nil {
		t.Error("非法日期应报错")
	}
}
