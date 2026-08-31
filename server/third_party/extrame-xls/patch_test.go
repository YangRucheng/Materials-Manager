package xls

import "testing"

// vendored 补丁行为锁定测试：运行方式 cd third_party/extrame-xls && go test ./...
// （nested module，不参与主模块 go test ./...）

func TestClassifyNumberFormat(t *testing.T) {
	cases := []struct {
		fmtStr     string
		date, time bool
	}{
		{"General", false, false},
		{"@", false, false},
		{"0", false, false},
		{"0.00", false, false},
		{"#,##0", false, false},
		{"#,##0.00", false, false},
		{"0_);(0)", false, false},
		{"0.00E+00", false, false},
		{"_(\"¥\")* #,##0", false, false},
		{"yyyy\"年\"m\"月\"d\"日\"", true, false},
		{"yyyy-mm-dd", true, false},
		{"m/d/yy", true, false},
		{"m/d/yy h:mm", true, false},
		{"h:mm AM/PM", false, true},
		{"mm:ss.0", false, true},
		{"h:mm:ss", false, true},
	}
	for _, tc := range cases {
		date, timeOnly, hasTime := classifyNumberFormat(tc.fmtStr)
		if date != tc.date || timeOnly != tc.time || (hasTime && !tc.date && !tc.time) {
			t.Errorf("classifyNumberFormat(%q) = (%v,%v,%v), want date=%v time=%v", tc.fmtStr, date, timeOnly, hasTime, tc.date, tc.time)
		}
	}
}

func encodeIntRK(v int32, divideBy100 bool) RK {
	// RK = (30 位有符号整数值 << 2) | bit1(整数标志) | bit0(除以 100 标志)
	rk := RK(uint32(v)<<2) | 2
	if divideBy100 {
		rk |= 1
	}
	return rk
}

func TestRKNumberDecode(t *testing.T) {
	cases := []struct {
		rk   RK
		want string
	}{
		{encodeIntRK(1, false), "1"},
		{encodeIntRK(-5, false), "-5"},    // 原版（无符号右移）会解码成巨大正数
		{encodeIntRK(150, true), "1.5"},   // 整数 ×1/100
		{encodeIntRK(-250, true), "-2.5"}, // 负数 ×1/100
	}
	for _, tc := range cases {
		if got := tc.rk.String(); got != tc.want {
			t.Errorf("RK(%#x).String()=%q want %q", uint32(tc.rk), got, tc.want)
		}
	}
}

func TestFormulaColCachedResult(t *testing.T) {
	newCol := func(result [8]byte, flags uint16) *FormulaCol {
		c := &FormulaCol{}
		c.Header.Result = result
		c.Header.Flags = flags
		return c
	}
	wb := &WorkBook{}
	// 数值缓存：2.0 的小端字节（byte6/7 非 FF FF）
	c := newCol([8]byte{0, 0, 0, 0, 0, 0, 0, 0x40}, 0)
	if got := c.String(wb)[0]; got != "2" {
		t.Errorf("numeric cached = %q, want 2", got)
	}
	// 字符串缓存（byte6/7 = FF FF，byte0 = 0）→ 值来自 pending STRING 记录
	c = newCol([8]byte{0, 0, 0, 0, 0, 0, 0xff, 0xff}, 3)
	c.RenderedValue = "正常"
	if got := c.String(wb)[0]; got != "正常" {
		t.Errorf("string cached = %q, want 正常", got)
	}
	if !c.resultIsString() {
		t.Error("resultIsString should be true for byte0=0, byte6/7=FF FF")
	}
	// 布尔缓存：byte0=1, byte2=1
	c = newCol([8]byte{1, 0, 1, 0, 0, 0, 0xff, 0xff}, 1)
	if got := c.String(wb)[0]; got != "TRUE" {
		t.Errorf("bool cached = %q, want TRUE", got)
	}
	// 错误缓存：byte0=2
	c = newCol([8]byte{2, 0, 0x07, 0, 0, 0, 0xff, 0xff}, 2)
	if got := c.String(wb)[0]; got != "#ERROR" {
		t.Errorf("error cached = %q, want #ERROR", got)
	}
	// 空结果缓存：byte0=3 → 空串（等价 xlwt 写手未存结果）
	c = newCol([8]byte{3, 0, 0, 0, 0, 0, 0xff, 0xff}, 0)
	if got := c.String(wb)[0]; got != "" {
		t.Errorf("empty cached = %q, want empty", got)
	}
}

func TestParseBiff8StringLayouts(t *testing.T) {
	// 布局 A（Excel/xlrd 实际行为）：Cch(2) + Option(1) + 8bit 字符
	payload := []byte{5, 0, 0, 'H', 'e', 'l', 'l', 'o'}
	if s, ok := parseBiff8String(payload); !ok || s != "Hello" {
		t.Errorf("layout A latin1 = %q,%v want Hello,true", s, ok)
	}
	// 布局 A：高字节标志 → UTF-16LE
	payload = []byte{2, 0, 1, 'A', 0, 0x4B, 0x4E} // 2 chars: 'A', '之'(U+4E4B)
	if s, ok := parseBiff8String(payload); !ok || s != "A之" {
		t.Errorf("layout A utf16 = %q,%v want A之,true", s, ok)
	}
	// 布局 B（OOo 文档）：Row(2) Col(2) Cch(2) + 8bit 字符
	payload = []byte{1, 0, 5, 0, 4, 0, 'O', 'K', '!', '!'}
	if s, ok := parseBiff8String(payload); !ok || s != "OK!!" {
		t.Errorf("layout B = %q,%v want OK!!,true", s, ok)
	}
}
