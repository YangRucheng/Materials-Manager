// Package serialize 提供与 Python 后端（Pydantic）完全一致的 JSON 序列化：
//   - datetime 三种格式（Z / +00:00 / naive）
//   - date（YYYY-MM-DD）
//   - Decimal 字符串（format(normalize(), 'f')）
package serialize

import (
	"math/big"
	"strings"
	"time"

	"github.com/shopspring/decimal"
)

// ============ time ============

const timeLayoutNoFrac = "2006-01-02T15:04:05"
const timeLayoutFrac = "2006-01-02T15:04:05.000000"
const dateLayout = "2006-01-02"

// FormatUTCZ 复刻 Pydantic v2 对 aware UTC datetime 的默认序列化：
// 微秒为 0 -> 无小数；微秒非 0 -> 恒 6 位小数（不裁剪尾零）+ "Z"。
func FormatUTCZ(t time.Time) string {
	t = t.UTC()
	if t.Nanosecond() == 0 {
		return t.Format(timeLayoutNoFrac) + "Z"
	}
	return t.Format(timeLayoutFrac) + "Z"
}

// FormatOffset 复刻 UtcDateTime 的自定义序列化（datetime.isoformat()）：
// ...+00:00 后缀，小数规则同上。
func FormatOffset(t time.Time) string {
	t = t.UTC()
	if t.Nanosecond() == 0 {
		return t.Format(timeLayoutNoFrac) + "+00:00"
	}
	return t.Format(timeLayoutFrac) + "+00:00"
}

// FormatNaive 复刻 Pydantic v2 对 naive datetime 的序列化（无时区后缀）。
func FormatNaive(t time.Time) string {
	t = t.UTC()
	if t.Nanosecond() == 0 {
		return t.Format(timeLayoutNoFrac)
	}
	return t.Format(timeLayoutFrac)
}

// FormatDate 输出 YYYY-MM-DD。
func FormatDate(t time.Time) string {
	return t.UTC().Format(dateLayout)
}

// UTCZTime 是输出为 "Z" 格式的 time.Time（Pydantic 默认 datetime 字段）。
type UTCZTime time.Time

func (t UTCZTime) MarshalJSON() ([]byte, error) {
	return []byte(`"` + FormatUTCZ(time.Time(t)) + `"`), nil
}

// OffsetTime 是输出为 "+00:00" 格式的 time.Time（UtcDateTime 字段）。
type OffsetTime time.Time

func (t OffsetTime) MarshalJSON() ([]byte, error) {
	return []byte(`"` + FormatOffset(time.Time(t)) + `"`), nil
}

// NaiveTime 是输出为无时区后缀的 time.Time。
type NaiveTime time.Time

func (t NaiveTime) MarshalJSON() ([]byte, error) {
	return []byte(`"` + FormatNaive(time.Time(t)) + `"`), nil
}

// Date 是输出为 YYYY-MM-DD 的日期。
type Date time.Time

func (d Date) MarshalJSON() ([]byte, error) {
	return []byte(`"` + FormatDate(time.Time(d)) + `"`), nil
}

// ParseDateTime 解析请求中的 datetime 字符串（Python datetime.fromisoformat 兼容子集，
// 支持 "Z" 与 "+hh:mm" 时区后缀；无后缀视为 naive，返回 UTC naive time.Time）。
func ParseDateTime(value string) (time.Time, error) {
	text := strings.TrimSpace(value)
	if text == "" {
		return time.Time{}, errEmptyTime
	}
	// 替换 Z
	text = strings.Replace(text, "Z", "+00:00", 1)
	for _, layout := range []string{
		"2006-01-02T15:04:05.999999999-07:00",
		"2006-01-02T15:04:05.999999999",
		"2006-01-02T15:04:05-07:00",
		"2006-01-02T15:04:05",
		"2006-01-02",
	} {
		if t, err := time.Parse(layout, text); err == nil {
			return t.UTC(), nil
		}
	}
	return time.Time{}, errInvalidTime
}

var (
	errEmptyTime   = errStr("空时间字符串")
	errInvalidTime = errStr("无效的时间格式")
)

type errStr string

func (e errStr) Error() string { return string(e) }

// UTCNow 返回当前 UTC 时间（naive 语义，Nanosecond 归零到微秒与 Python 对齐不必要，
// Go 直接保留纳秒；序列化时自动处理）。
func UTCNow() time.Time { return time.Now().UTC() }

// ============ decimal ============

// DecimalToString 复刻 Python format(value.normalize(), 'f')：
// 去尾零、科学计数展开为普通十进制字符串。
func DecimalToString(d decimal.Decimal) string {
	if d.IsZero() {
		return "0"
	}
	coeff := new(big.Int).Set(d.Coefficient())
	exp := d.Exponent() // 负值 = 小数位
	ten := big.NewInt(10)
	for exp < 0 {
		q, r := new(big.Int).QuoRem(coeff, ten, new(big.Int))
		if r.Sign() == 0 {
			coeff = q
			exp++
		} else {
			break
		}
	}
	if exp >= 0 {
		if exp > 0 {
			coeff.Mul(coeff, new(big.Int).Exp(ten, big.NewInt(int64(exp)), nil))
		}
		return coeff.String()
	}
	digits := coeff.String()
	frac := int(-exp)
	if len(digits) <= frac {
		return "0." + strings.Repeat("0", frac-len(digits)) + digits
	}
	intPart := digits[:len(digits)-frac]
	fracPart := digits[len(digits)-frac:]
	return intPart + "." + fracPart
}

// DecimalJSON 用于响应结构体：输出为字符串（与 Pydantic json_encoders 一致）。
type DecimalJSON struct {
	decimal.Decimal
}

func (d DecimalJSON) MarshalJSON() ([]byte, error) {
	return []byte(`"` + DecimalToString(d.Decimal) + `"`), nil
}

func (d *DecimalJSON) UnmarshalJSON(data []byte) error {
	s := strings.TrimSpace(string(data))
	s = strings.Trim(s, `"`)
	dec, err := decimal.NewFromString(s)
	if err != nil {
		return err
	}
	d.Decimal = dec
	return nil
}

// ParseDecimalString 解析请求中的十进制字符串。
func ParseDecimalString(s string) (decimal.Decimal, error) {
	return decimal.NewFromString(strings.TrimSpace(s))
}
