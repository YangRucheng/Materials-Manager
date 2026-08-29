// Package aiclient OpenAI 兼容 chat/completions 客户端（非流式扩词）。
package aiclient

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const connectTimeout = 3 * time.Second
const readTimeout = 10 * time.Second

// SystemPrompt 要求模型返回 JSON。
const SystemPrompt = `你是物料名称规范化与同义词扩展助手。用户给出一个物料关键词，
请给出 1 到 6 个同义词/近义词（含原词）。只返回 JSON，格式：{"expansions":[["原词","同义词1"],["原词","同义词2"]]}`

// ExpandRequest 扩词请求。
type ExpandRequest struct {
	Endpoint string
	APIKey   string
	Model    string
	Value    string
	Test     bool
}

// ChatMessage 消息。
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// Expand 调用上游扩词，返回同义词列表（含原词）。
func Expand(req ExpandRequest) ([]string, error) {
	endpoint := strings.TrimSuffix(req.Endpoint, "/")
	if !strings.HasSuffix(endpoint, "/chat/completions") {
		endpoint += "/chat/completions"
	}
	payload := map[string]any{
		"model":       req.Model,
		"stream":      false,
		"temperature": 0,
		"max_tokens":  180,
		"messages": []ChatMessage{
			{Role: "system", Content: SystemPrompt},
			{Role: "user", Content: req.Value},
		},
	}
	if strings.HasPrefix(req.Model, "glm-") {
		payload["thinking"] = map[string]any{"type": "disabled"}
		payload["response_format"] = map[string]any{"type": "json_object"}
	}
	body, _ := json.Marshal(payload)
	client := &http.Client{Timeout: readTimeout}
	httpReq, err := http.NewRequest("POST", endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("AI_REQUEST_FAILED")
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+req.APIKey)
	resp, err := client.Do(httpReq)
	if err != nil {
		if strings.Contains(err.Error(), "timeout") || strings.Contains(err.Error(), "Client.Timeout") {
			return nil, fmt.Errorf("AI_RESPONSE_TIMEOUT")
		}
		return nil, fmt.Errorf("AI_CONNECTION_FAILED")
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 401 || resp.StatusCode == 403 {
		return nil, fmt.Errorf("AI_AUTH_FAILED")
	}
	if resp.StatusCode == 404 {
		return nil, fmt.Errorf("AI_ENDPOINT_NOT_FOUND")
	}
	if resp.StatusCode == 429 {
		return nil, fmt.Errorf("AI_RATE_LIMITED")
	}
	if resp.StatusCode >= 400 && resp.StatusCode < 500 {
		return nil, fmt.Errorf("AI_REQUEST_REJECTED")
	}
	if resp.StatusCode >= 500 {
		return nil, fmt.Errorf("AI_UPSTREAM_FAILED")
	}
	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.Unmarshal(data, &result); err != nil || len(result.Choices) == 0 {
		return nil, fmt.Errorf("AI_INVALID_RESPONSE")
	}
	content := result.Choices[0].Message.Content
	return parseExpansions(content, req.Value)
}

// parseExpansions 解析模型返回的 JSON（容忍 ```json 围栏）。
func parseExpansions(content, original string) ([]string, error) {
	text := strings.TrimSpace(content)
	text = strings.TrimPrefix(text, "```json")
	text = strings.TrimSuffix(text, "```")
	text = strings.TrimSpace(text)
	var parsed struct {
		Expansions [][]string `json:"expansions"`
	}
	if err := json.Unmarshal([]byte(text), &parsed); err != nil {
		// 尝试提取第一个 { ... }
		start := strings.IndexByte(text, '{')
		end := strings.LastIndexByte(text, '}')
		if start >= 0 && end > start {
			_ = json.Unmarshal([]byte(text[start:end+1]), &parsed)
		}
	}
	seen := map[string]bool{}
	var out []string
	for _, pair := range parsed.Expansions {
		if len(pair) >= 2 {
			syn := strings.TrimSpace(pair[1])
			if syn != "" && !seen[syn] {
				seen[syn] = true
				out = append(out, syn)
			}
		}
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("AI_INVALID_RESPONSE")
	}
	return out, nil
}
