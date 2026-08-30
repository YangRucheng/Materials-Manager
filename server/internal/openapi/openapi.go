// Package openapi 内嵌并解析 docs/openapi.yaml 契约（MCP 目录、契约校验、openapi.json 输出共用）。
package openapi

import (
	_ "embed"
	"encoding/json"
	"sync"

	"gopkg.in/yaml.v3"
)

//go:embed openapi.yaml
var openapiYAML []byte

var (
	once       sync.Once
	spec       map[string]any
	parseError error
	jsonBytes  []byte
)

func load() {
	once.Do(func() {
		spec = map[string]any{}
		if err := yaml.Unmarshal(openapiYAML, &spec); err != nil {
			parseError = err
			return
		}
		jsonBytes, parseError = json.Marshal(spec)
	})
}

// JSON 返回 openapi 的 JSON 表示（/api/v1/openapi.json 使用）。
func JSON() ([]byte, error) {
	load()
	if parseError != nil {
		return nil, parseError
	}
	return jsonBytes, nil
}

// Spec 返回解析后的契约结构。
func Spec() (map[string]any, error) {
	load()
	if parseError != nil {
		return nil, parseError
	}
	return spec, nil
}

// YAMLBytes 返回原始 YAML 字节。
func YAMLBytes() []byte { return openapiYAML }
