// Package service 通用工具函数（等价 backend/app/services/common.py）。
package service

import (
	"crypto/sha256"
	"encoding/hex"
	"math/big"
	"strings"

	"github.com/shopspring/decimal"
	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
)

// NormalizedText 复刻 Python normalized_text：NFKC + 空白折叠 + strip + casefold。
func NormalizedText(value string) string {
	joined := strings.Join(strings.Fields(norm.NFKC.String(value)), " ")
	return cases.Fold().String(joined)
}

// IdentityHash 复刻 identity_hash：name\0model_spec\0unit_name 的 SHA-256 hex。
func IdentityHash(name, modelSpec, unitName string) string {
	raw := NormalizedText(name) + "\x00" + NormalizedText(modelSpec) + "\x00" + NormalizedText(unitName)
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}

// SplitOrSearchTerms 复刻 split_or_search_terms：按 | 或 ｜ 拆词去重。
func SplitOrSearchTerms(value string) []string {
	if value == "" {
		return nil
	}
	parts := strings.FieldsFunc(value, func(r rune) bool { return r == '|' || r == '｜' })
	seen := map[string]bool{}
	var terms []string
	for _, part := range parts {
		term := strings.TrimSpace(part)
		if term != "" && !seen[term] {
			seen[term] = true
			terms = append(terms, term)
		}
	}
	return terms
}

// EscapeLike 复刻 SQLAlchemy contains(autoescape=True)：转义 % _ \。
func EscapeLike(value string) string {
	replacer := strings.NewReplacer("\\", "\\\\", "%", "\\%", "_", "\\_")
	return replacer.Replace(value)
}

// ContainsAnyClause 返回 OR 搜索的 where 片段与参数：
// 对每个词 × 每列生成 col LIKE '%term%'（autoescape）。列名由调用方传入 SQL 列名。
func ContainsAnyClause(columns []string, value string) (clause string, args []any) {
	terms := SplitOrSearchTerms(value)
	if len(terms) == 0 {
		return "", nil
	}
	var conds []string
	for _, term := range terms {
		escaped := "%" + EscapeLike(term) + "%"
		for _, col := range columns {
			conds = append(conds, col+" LIKE ?")
			args = append(args, escaped)
		}
	}
	return "(" + strings.Join(conds, " OR ") + ")", args
}

// ValidateQuantityPrecision 复刻 validate_quantity_precision：最多 1 位小数。
func ValidateQuantityPrecision(quantity decimal.Decimal) *apperrors.AppError {
	if FractionDigits(quantity) > 1 {
		return apperrors.New("INVALID_QUANTITY_PRECISION", "数量最多保留 1 位小数", 0,
			map[string]any{"quantity": quantity.String(), "decimal_places": 1})
	}
	return nil
}

// FractionDigits 返回去掉尾零后的小数位数。
func FractionDigits(d decimal.Decimal) int {
	if d.IsZero() {
		return 0
	}
	coeff := new(big.Int).Set(d.Coefficient())
	exp := d.Exponent()
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
		return 0
	}
	return int(-exp)
}

// Zero 常量。
var Zero = decimal.NewFromInt(0)
