// Package mcp MCP 服务（Streamable HTTP），等价 mcp_server.py。
package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"regexp"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/openapi"
	"github.com/yangrucheng/materials-manager/server/internal/security"
	"time"
)

var pathParamRe = regexp.MustCompile(`\{([^}]+)\}`)

// Server MCP 服务。
type Server struct {
	cfg    *config.Config
	db     *gorm.DB
	engine *gin.Engine
}

// New 构造 MCP Streamable HTTP handler（含令牌认证）。
func New(cfg *config.Config, db *gorm.DB, engine *gin.Engine) http.Handler {
	s := &Server{cfg: cfg, db: db, engine: engine}
	mcpServer := server.NewMCPServer("spare-parts-management", "1.0.0")
	mcpServer.AddTool(mcp.NewTool("system_whoami",
		mcp.WithDescription("返回当前 MCP 令牌对应的管理端用户及角色。"),
	), s.whoami)
	mcpServer.AddTool(mcp.NewTool("operations_list",
		mcp.WithDescription("列出可调用的业务操作。category 按接口标签筛选，keyword 按名称和说明搜索。"),
		mcp.WithString("category", mcp.Required(), mcp.Description("按标签筛选")),
		mcp.WithString("keyword", mcp.Description("按名称和说明搜索")),
	), s.operationsList)
	mcpServer.AddTool(mcp.NewTool("operation_describe",
		mcp.WithDescription("返回指定业务操作的路径参数、查询参数、请求体和响应契约。"),
		mcp.WithString("operation_id", mcp.Required(), mcp.Description("操作 ID")),
	), s.operationDescribe)
	mcpServer.AddTool(mcp.NewTool("operation_call",
		mcp.WithDescription("调用一个已登记的业务操作；附件使用 file.content_base64 传入。"),
		mcp.WithString("operation_id", mcp.Required(), mcp.Description("操作 ID")),
		mcp.WithObject("path_params", mcp.Description("路径参数")),
		mcp.WithObject("query", mcp.Description("查询参数")),
		mcp.WithObject("body", mcp.Description("请求体")),
	), s.operationCall)
	streamable := server.NewStreamableHTTPServer(mcpServer)
	return s.authMiddleware(streamable)
}

// authMiddleware 令牌认证：?token= / X-API-Token / Bearer。
func (s *Server) authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		token := ""
		if q := r.URL.Query().Get("token"); q != "" {
			token = q
		} else if h := r.Header.Get("X-API-Token"); h != "" {
			token = h
		} else if authz := r.Header.Get("Authorization"); strings.HasPrefix(authz, "Bearer ") {
			token = strings.TrimPrefix(authz, "Bearer ")
		}
		if token == "" {
			w.WriteHeader(401)
			_, _ = w.Write([]byte(`{"code":"INVALID_TOKEN","message":"缺少 MCP 接口令牌"}`))
			return
		}
		var user models.User
		err := s.db.Where("api_token_hash = ?", security.HashAPIToken(token)).First(&user).Error
		if err != nil || !user.Enabled {
			w.WriteHeader(401)
			_, _ = w.Write([]byte(`{"code":"INVALID_TOKEN","message":"MCP 接口令牌无效或用户已停用"}`))
			return
		}
		ctx := context.WithValue(r.Context(), ctxKeyIdentity{}, identity{
			ID: user.ID, Username: user.Username, DisplayName: user.DisplayName, Role: user.Role,
		})
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

type ctxKeyIdentity struct{}

type identity struct {
	ID          int64  `json:"id"`
	Username    string `json:"username"`
	DisplayName string `json:"display_name"`
	Role        string `json:"role"`
}

func (s *Server) whoami(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	id := ctx.Value(ctxKeyIdentity{}).(identity)
	return jsonResult(id)
}

// operationCatalog 从 openapi 生成操作目录。
func operationCatalog() (map[string]map[string]any, error) {
	spec, err := openapi.Spec()
	if err != nil {
		return nil, err
	}
	paths, _ := spec["paths"].(map[string]any)
	excluded := map[string]bool{
		"/api/v1/auth/login": true, "/api/v1/auth/refresh": true,
	}
	catalog := map[string]map[string]any{}
	for p, item := range paths {
		if excluded[p] || strings.HasPrefix(p, "/api/v1/agent/database") || strings.HasPrefix(p, "/api/v1/mini-program/") {
			continue
		}
		pathItem, _ := item.(map[string]any)
		for method, op := range pathItem {
			opMap, ok := op.(map[string]any)
			if !ok {
				continue
			}
			opID, _ := opMap["operationId"].(string)
			if opID == "" {
				continue
			}
			catalog[opID] = map[string]any{
				"operation_id": opID, "method": strings.ToUpper(method), "path": p,
				"summary":     opMap["summary"],
				"description": opMap["description"],
				"tags":        opMap["tags"],
				"parameters":  opMap["parameters"],
				"request_body": opMap["requestBody"],
				"responses":   opMap["responses"],
			}
		}
	}
	return catalog, nil
}

func (s *Server) operationsList(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	args := req.GetArguments()
	category, _ := args["category"].(string)
	catalog, err := operationCatalog()
	if err != nil {
		return jsonResult(map[string]any{"error": err.Error()})
	}
	operations := make([]map[string]any, 0, len(catalog))
	for _, item := range catalog {
		if category != "" {
			matched := false
			if tags, ok := item["tags"].([]any); ok {
				for _, tag := range tags {
					if strings.Contains(strings.ToLower(fmt.Sprint(tag)), strings.ToLower(category)) {
						matched = true
					}
				}
			}
			if !matched {
				continue
			}
		}
		operations = append(operations, item)
	}
	concise := make([]map[string]any, 0, len(operations))
	for _, item := range operations {
		concise = append(concise, map[string]any{
			"operation_id": item["operation_id"], "method": item["method"],
			"path": item["path"], "summary": item["summary"], "tags": item["tags"],
		})
	}
	return jsonResult(map[string]any{"count": len(concise), "operations": concise})
}

func (s *Server) operationDescribe(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	opID := req.GetString("operation_id", "")
	catalog, err := operationCatalog()
	if err != nil {
		return jsonResult(map[string]any{"error": err.Error()})
	}
	op, ok := catalog[opID]
	if !ok {
		return jsonResult(map[string]any{"error": fmt.Sprintf("未知或不允许的 operation_id: %s", opID)})
	}
	return jsonResult(op)
}

func (s *Server) operationCall(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	args := req.GetArguments()
	opID, _ := args["operation_id"].(string)
	catalog, err := operationCatalog()
	if err != nil {
		return jsonResult(map[string]any{"error": err.Error()})
	}
	op, ok := catalog[opID]
	if !ok {
		return jsonResult(map[string]any{"error": fmt.Sprintf("未知或不允许的 operation_id: %s", opID)})
	}
	id := ctx.Value(ctxKeyIdentity{}).(identity)
	var user models.User
	_ = s.db.First(&user, id.ID).Error
	token := user.APITokenHash
	_ = token
	// 通过 httptest 调用内部路由（用 API 令牌重查）
	var apiToken string
	_ = apiToken
	// 直接以令牌哈希伪造调用：使用 X-API-Token 需要明文，这里用 Bearer 重新签发不现实；
	// 简化：以当前身份直接注入（内部调用可信）。
	path := buildPath(op["path"].(string), args["path_params"])
	method := strings.ToUpper(op["method"].(string))
	var bodyReader *strings.Reader
	if body, ok := args["body"]; ok {
		raw, _ := json.Marshal(body)
		bodyReader = strings.NewReader(string(raw))
	} else {
		bodyReader = strings.NewReader("")
	}
	httpReq := httptest.NewRequest(method, "/api/v1"+strings.TrimPrefix(path, "/api/v1"), bodyReader)
	if query, ok := args["query"].(map[string]any); ok {
		q := httpReq.URL.Query()
		for k, v := range query {
			q.Set(k, fmt.Sprint(v))
		}
		httpReq.URL.RawQuery = q.Encode()
	}
	httpReq.Header.Set("Content-Type", "application/json")
	// 内部调用：签发临时管理端令牌
	if accessToken, err := security.NewAccessToken(s.cfg.JWTSecret, s.cfg.JWTAlgorithm, id.ID, 5*time.Minute); err == nil {
		httpReq.Header.Set("Authorization", "Bearer "+accessToken)
	}
	rec := httptest.NewRecorder()
	s.engine.ServeHTTP(rec, httpReq)
	contentType := rec.Header().Get("Content-Type")
	if rec.Code == 204 || len(rec.Body.Bytes()) == 0 {
		return jsonResult(map[string]any{"status_code": rec.Code, "data": nil})
	}
	if strings.Contains(contentType, "application/json") {
		var data any
		_ = json.Unmarshal(rec.Body.Bytes(), &data)
		return jsonResult(map[string]any{"status_code": rec.Code, "data": data})
	}
	return jsonResult(map[string]any{
		"status_code": rec.Code, "content_type": contentType,
		"filename": "", "content_base64": base64Encode(rec.Body.Bytes()),
	})
}

func buildPath(template string, pathParams any) string {
	params, _ := pathParams.(map[string]any)
	result := template
	for _, m := range pathParamRe.FindAllStringSubmatch(template, -1) {
		name := m[1]
		value, ok := params[name].(string)
		if !ok {
			value = ""
		}
		result = strings.Replace(result, "{"+name+"}", url.PathEscape(value), 1)
	}
	return result
}

func jsonResult(v any) (*mcp.CallToolResult, error) {
	raw, _ := json.Marshal(v)
	return &mcp.CallToolResult{
		Content: []mcp.Content{
			mcp.TextContent{Type: "text", Text: string(raw)},
		},
		StructuredContent: v,
	}, nil
}

func base64Encode(data []byte) string {
	const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
	var out []byte
	for i := 0; i < len(data); i += 3 {
		var b [3]byte
		n := copy(b[:], data[i:])
		out = append(out, chars[b[0]>>2])
		out = append(out, chars[(b[0]&0x03)<<4|b[1]>>4])
		if n > 1 {
			out = append(out, chars[(b[1]&0x0f)<<2|b[2]>>6])
		} else {
			out = append(out, '=')
		}
		if n > 2 {
			out = append(out, chars[b[2]&0x3f])
		} else {
			out = append(out, '=')
		}
	}
	return string(out)
}
