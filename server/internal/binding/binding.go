// Package binding 提供严格 JSON 请求体解码，复刻 Pydantic RequestModel 行为：
//   - extra="forbid"：未知字段 -> 422 extra_forbidden
//   - str_strip_whitespace：字符串字段去首尾空白
//   - 类型错误 -> 422（int/float/bool 解析错误等）
//   - 必填缺失 -> 422
//
// 校验错误以 Pydantic 风格的 details.errors 数组返回。
package binding

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"reflect"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/go-playground/validator/v10"

	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
)

var validate = validator.New()

// ErrorItem 对应 Pydantic errors 数组中的一项。
type ErrorItem struct {
	Type  string         `json:"type"`
	Loc   []any          `json:"loc"`
	Msg   string         `json:"msg"`
	Input any            `json:"input"`
	Ctx   map[string]any `json:"ctx,omitempty"`
}

// ValidationDetails 对应 FastAPI RequestValidationError 的 details。
type ValidationDetails struct {
	Errors []ErrorItem `json:"errors"`
}

// ValidationError 返回 422 AppError。
func ValidationError(items []ErrorItem) *apperrors.AppError {
	if items == nil {
		items = []ErrorItem{}
	}
	return apperrors.New("VALIDATION_ERROR", "请求参数校验失败", 422,
		map[string]any{"errors": items})
}

// Body 严格解码 JSON 请求体并做基础类型/未知字段校验 + 空白裁剪 + struct 校验。
func Body(c *gin.Context, dst any) *apperrors.AppError {
	decoder := json.NewDecoder(c.Request.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(dst); err != nil {
		var syntaxErr *json.SyntaxError
		var typeErr *json.UnmarshalTypeError
		switch {
		case errors.Is(err, io.EOF):
			return ValidationError([]ErrorItem{
				{Type: "missing", Loc: []any{"body"}, Msg: "Field required", Input: nil},
			})
		case errors.As(err, &typeErr):
			return typeConversionError(typeErr)
		case errors.As(err, &syntaxErr):
			return ValidationError([]ErrorItem{
				{Type: "json_invalid", Loc: []any{"body"}, Msg: "JSON decode error", Input: nil},
			})
		default:
			// 未知字段错误来自 encoding/json 的错误消息
			if strings.Contains(err.Error(), "unknown field") {
				field := strings.TrimPrefix(err.Error(), "json: unknown field ")
				field = strings.Trim(field, `"`)
				return ValidationError([]ErrorItem{
					{Type: "extra_forbidden", Loc: []any{"body", field},
						Msg: "Extra inputs are not permitted", Input: field},
				})
			}
			return ValidationError([]ErrorItem{
				{Type: "value_error", Loc: []any{"body"}, Msg: err.Error(), Input: nil},
			})
		}
	}
	// 允许多余空白：再读一个 token 应为 EOF
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return ValidationError([]ErrorItem{
			{Type: "value_error", Loc: []any{"body"}, Msg: "Extra inputs are not permitted", Input: nil},
		})
	}
	TrimStringFields(dst)
	if err := validate.Struct(dst); err != nil {
		return structValidationError(err)
	}
	return nil
}

// TrimStringFields 反射递归去除字符串字段首尾空白（等价 str_strip_whitespace）。
func TrimStringFields(v any) {
	rv := reflect.ValueOf(v)
	trimValue(rv)
}

func trimValue(rv reflect.Value) {
	for rv.Kind() == reflect.Ptr {
		if rv.IsNil() {
			return
		}
		rv = rv.Elem()
	}
	switch rv.Kind() {
	case reflect.String:
		rv.SetString(strings.TrimSpace(rv.String()))
	case reflect.Struct:
		for i := 0; i < rv.NumField(); i++ {
			trimValue(rv.Field(i))
		}
	case reflect.Slice:
		for i := 0; i < rv.Len(); i++ {
			trimValue(rv.Index(i))
		}
	case reflect.Map:
		iter := rv.MapRange()
		for iter.Next() {
			trimValue(iter.Value())
		}
	}
}

func typeConversionError(typeErr *json.UnmarshalTypeError) *apperrors.AppError {
	field := typeErr.Field
	if field == "" {
		field = "body"
	}
	expected := jsonTypeName(typeErr.Type)
	input := typeErr.Value
	switch expected {
	case "int":
		return ValidationError([]ErrorItem{
			{Type: "int_parsing", Loc: []any{"body", field},
				Msg: "Input should be a valid integer, unable to parse string as an integer", Input: input},
		})
	case "float":
		return ValidationError([]ErrorItem{
			{Type: "float_parsing", Loc: []any{"body", field},
				Msg: "Input should be a valid number, unable to parse string as a number", Input: input},
		})
	case "bool":
		return ValidationError([]ErrorItem{
			{Type: "bool_parsing", Loc: []any{"body", field},
				Msg: "Input should be a valid boolean, unable to interpret input", Input: input},
		})
	default:
		return ValidationError([]ErrorItem{
			{Type: "value_error", Loc: []any{"body", field},
				Msg: fmt.Sprintf("Input should be a valid %s", expected), Input: input},
		})
	}
}

func jsonTypeName(t reflect.Type) string {
	switch t.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return "int"
	case reflect.Float32, reflect.Float64:
		return "float"
	case reflect.Bool:
		return "bool"
	default:
		return strings.ToLower(t.String())
	}
}

func structValidationError(err error) *apperrors.AppError {
	var verr validator.ValidationErrors
	if !errors.As(err, &verr) {
		return ValidationError(nil)
	}
	items := make([]ErrorItem, 0, len(verr))
	for _, fe := range verr {
		field := fieldJSONName(fe.StructField())
		items = append(items, ErrorItem{
			Type:  "value_error",
			Loc:   []any{"body", field},
			Msg:   fe.Tag() + " validation failed: " + fe.Param(),
			Input: fe.Value(),
		})
	}
	return ValidationError(items)
}

func fieldJSONName(structField string) string {
	return structField
}

// ParseQuery 解析并校验查询参数（整型/枚举），生成 FastAPI 风格 loc=["query", name]。
func ParseQuery(c *gin.Context, name string, fn func(value string) error) *apperrors.AppError {
	value := c.Query(name)
	if err := fn(value); err != nil {
		if appErr, ok := err.(*apperrors.AppError); ok {
			return appErr
		}
	}
	return nil
}
