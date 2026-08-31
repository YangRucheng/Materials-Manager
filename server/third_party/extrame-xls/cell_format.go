// 本文件为本仓库对 vendored extrame/xls（Apache-2.0）的补丁：
// 原版把所有用户自定义数字格式（fNo>=164）一律当日期渲染成 RFC3339，
// 导致 RK/MULRK/NUMBER 存储的普通数字（如库存数量）输出成 "1899-12-31T00:00:00Z"
// 这类无法解析的字符串（华星导入 HUAXING_IMPORT_INVALID_QUANTITY 的根因）。
// 这里按 Excel 数字格式串本身判别日期/时间/数字（思路等价 xlrd 的 format 分类）。
package xls

import (
	"strings"
)

// 内置数字格式编号中的日期/时间类（ECMA-376 2.5.4，含 27-36/50-58 的东亚区域变体）。
var builtinDateFormat = map[uint16]uint8{} // 0=date, 1=date+time, 2=time only

func init() {
	dateOnly := []uint16{14, 15, 16, 17, 22, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 50, 51, 52, 53, 54, 55, 56, 57, 58}
	for _, id := range dateOnly {
		builtinDateFormat[id] = 0
	}
	for _, id := range []uint16{18, 19, 20, 21, 45, 46, 47} {
		builtinDateFormat[id] = 2 // time only
	}
	builtinDateFormat[22] = 1 // m/d/yy h:mm
}

// classifyNumberFormat 判别 Excel 数字格式串（思路等价 xlrd）：
// 去掉引号字面量、[条件/区域]段、_x 与 \x 转义字符后：
//   - 含 y/d → 日期格式（另含 h/s/: 则带时间）；
//   - 仅含 m 且无 h/s/: → 月份（日期格式）；
//   - 无 y/d 但含 h/s/:（含 mm:ss、h:mm AM/PM 等）→ 纯时间格式；
//   - 其余（General、#,##0、0.00、0_);(0)、@ 等）→ 数字格式。
func classifyNumberFormat(fmtStr string) (date, timeOnly, hasTime bool) {
	lower := strings.ToLower(strings.TrimSpace(stripFormatLiterals(fmtStr)))
	if lower == "" || lower == "general" || lower == "@" {
		return false, false, false
	}
	hasYD := strings.ContainsAny(lower, "yd")
	hasM := strings.Contains(lower, "m")
	hasHS := strings.ContainsAny(lower, "hs") || strings.Contains(lower, "am/pm") || strings.Contains(lower, ":")
	switch {
	case hasYD:
		return true, false, hasHS
	case hasM && !hasHS:
		return true, false, false
	case hasHS:
		return false, true, true
	default:
		return false, false, false
	}
}

// stripFormatLiterals 去掉格式串中的字面量部分，仅保留格式 token。
func stripFormatLiterals(fmtStr string) string {
	var b strings.Builder
	runes := []rune(fmtStr)
	inQuote := false
	for i := 0; i < len(runes); i++ {
		r := runes[i]
		switch {
		case inQuote:
			if r == '"' {
				inQuote = false
			}
		case r == '"':
			inQuote = true
		case r == '[':
			// [红色]/[$-804]/[>100] 等条件与区域段整体跳过
			for i < len(runes) && runes[i] != ']' {
				i++
			}
		case r == '\\':
			i++ // 转义单字符字面量
		case r == '_':
			i++ // 下划线+下一字符为字面量（对齐留白）
		case r == '*':
			i++ // 填充字符
		default:
			b.WriteRune(r)
		}
	}
	return b.String()
}

// formatNumberLikeCell 依据 XF 索引对应数字格式渲染 serial 数值：
// 日期/时间格式输出可读日期串（cellDate 可解析），否则输出原始数字。
// raw 为格式非日期时的原始数字串。返回 "" 表示 XF/格式不可用，调用方兜底。
func (wb *WorkBook) formatNumberLikeCell(xfIndex uint16, serial float64, raw string) string {
	isDate, isTime, hasTime := wb.xfFormatClass(xfIndex)
	if !isDate && !isTime {
		return raw
	}
	t := timeFromExcelTime(serial, wb.dateMode == 1)
	switch {
	case isTime: // 纯时间：输出时:分:秒（避免被当日期）
		return t.Format("15:04:05")
	case hasTime:
		return t.Format("2006-01-02 15:04:05")
	default:
		return t.Format("2006-01-02")
	}
}

// xfFormatClass 返回某 XF 的数字格式分类；无 XF/格式信息时按“非日期”处理。
func (wb *WorkBook) xfFormatClass(xfIndex uint16) (date, time, hasTime bool) {
	idx := int(xfIndex)
	if idx >= len(wb.Xfs) {
		return false, false, false
	}
	fNo := wb.Xfs[idx].formatNo()
	if kind, ok := builtinDateFormat[fNo]; ok {
		switch kind {
		case 0:
			return true, false, false
		case 1:
			return true, true, true
		default:
			return false, true, true
		}
	}
	if fNo >= 164 {
		if formatter := wb.Formats[fNo]; formatter != nil {
			date, time, hasTime = classifyNumberFormat(formatter.str)
		}
	}
	return date, time, hasTime
}
