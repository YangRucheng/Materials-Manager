package test

import (
	"bytes"
	"encoding/json"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

// doJSON 发起带 body 的请求并返回 recorder。
func doJSON(t *testing.T, r *gin.Engine, method, path string, body any, headers map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	var reader *bytes.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			t.Fatal(err)
		}
		reader = bytes.NewReader(data)
	} else {
		reader = bytes.NewReader(nil)
	}
	req := httptest.NewRequest(method, path, reader)
	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// login 登录并返回 Authorization 头。
func login(t *testing.T, r *gin.Engine, username string) map[string]string {
	t.Helper()
	w := doJSON(t, r, "POST", "/api/v1/auth/login", dto.LoginRequest{Username: username, Password: "123456"}, nil)
	if w.Code != 200 {
		t.Fatalf("登录 %s 失败 status=%d body=%s", username, w.Code, w.Body.String())
	}
	var resp dto.LoginResponse
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	return map[string]string{"Authorization": "Bearer " + resp.AccessToken}
}

func TestLoginSuccess(t *testing.T) {
	r := newTestEngine(t)
	w := doJSON(t, r, "POST", "/api/v1/auth/login", dto.LoginRequest{Username: "admin", Password: "123456"}, nil)
	if w.Code != 200 {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["token_type"] != "bearer" {
		t.Fatalf("token_type=%v", body["token_type"])
	}
	if body["access_token"] == "" || body["refresh_token"] == "" {
		t.Fatal("缺少令牌")
	}
	user := body["user"].(map[string]any)
	if user["username"] != "admin" || user["role"] != "SUPER_ADMIN" || user["version"] != float64(1) {
		t.Fatalf("user=%v", user)
	}
	// UserRead 不应含 api_token 字段
	if _, ok := user["api_token"]; ok {
		t.Fatal("LoginResponse.user 不应包含 api_token")
	}
}

func TestLoginWrongPassword(t *testing.T) {
	r := newTestEngine(t)
	w := doJSON(t, r, "POST", "/api/v1/auth/login", dto.LoginRequest{Username: "admin", Password: "wrong"}, nil)
	if w.Code != 401 {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["code"] != "INVALID_CREDENTIALS" || body["message"] != "用户名或密码错误" {
		t.Fatalf("body=%s", w.Body.String())
	}
}

func TestLoginUnknownUserSameError(t *testing.T) {
	r := newTestEngine(t)
	w := doJSON(t, r, "POST", "/api/v1/auth/login", dto.LoginRequest{Username: "nobody", Password: "123456"}, nil)
	if w.Code != 401 || !bytes.Contains(w.Body.Bytes(), []byte("INVALID_CREDENTIALS")) {
		t.Fatalf("未知用户应返回相同错误 status=%d body=%s", w.Code, w.Body.String())
	}
}

func TestAuthRequired(t *testing.T) {
	r := newTestEngine(t)
	w := testutil.Do(t, r, "GET", "/api/v1/auth/me", nil)
	if w.Code != 401 {
		t.Fatalf("status=%d", w.Code)
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["code"] != "UNAUTHORIZED" || body["message"] != "请先登录" {
		t.Fatalf("body=%s", w.Body.String())
	}
}

func TestMeAndRefresh(t *testing.T) {
	r := newTestEngine(t)
	headers := login(t, r, "admin")
	w := testutil.Do(t, r, "GET", "/api/v1/auth/me", headers)
	if w.Code != 200 {
		t.Fatalf("me status=%d", w.Code)
	}

	// 刷新
	refreshW := doJSON(t, r, "POST", "/api/v1/auth/login", dto.LoginRequest{Username: "admin", Password: "123456"}, nil)
	var loginResp dto.LoginResponse
	_ = json.Unmarshal(refreshW.Body.Bytes(), &loginResp)
	refreshResp := doJSON(t, r, "POST", "/api/v1/auth/refresh",
		dto.RefreshTokenRequest{RefreshToken: loginResp.RefreshToken}, nil)
	if refreshResp.Code != 200 {
		t.Fatalf("refresh status=%d body=%s", refreshResp.Code, refreshResp.Body.String())
	}
	var pair dto.TokenPairResponse
	_ = json.Unmarshal(refreshResp.Body.Bytes(), &pair)
	if pair.AccessToken == "" || pair.RefreshToken == "" || pair.TokenType != "bearer" {
		t.Fatalf("pair=%+v", pair)
	}
}

func TestUsersCRUD(t *testing.T) {
	r := newTestEngine(t)
	admin := login(t, r, "admin")

	// 列表
	list := testutil.Do(t, r, "GET", "/api/v1/users?page=1&page_size=10", admin)
	if list.Code != 200 {
		t.Fatalf("list status=%d", list.Code)
	}
	var pageResp dto.Page[dto.UserApiTokenRead]
	_ = json.Unmarshal(list.Body.Bytes(), &pageResp)
	if pageResp.Total != 4 || len(pageResp.Items) != 4 {
		t.Fatalf("total=%d len=%d", pageResp.Total, len(pageResp.Items))
	}
	// 列表 api_token 应为 null
	if pageResp.Items[0].APIToken != nil {
		t.Fatal("列表 api_token 应为 null")
	}

	// 创建（返回明文令牌一次）
	create := doJSON(t, r, "POST", "/api/v1/users",
		dto.UserCreate{Username: "newbie", Password: "secret1", DisplayName: "新用户", Role: "READ_ONLY"}, admin)
	if create.Code != 201 {
		t.Fatalf("create status=%d body=%s", create.Code, create.Body.String())
	}
	var created dto.UserApiTokenRead
	_ = json.Unmarshal(create.Body.Bytes(), &created)
	if created.APIToken == nil || len(*created.APIToken) != 36 {
		t.Fatalf("创建应返回一次明文令牌: %+v", created.APIToken)
	}
	// 用明文令牌访问
	tokenHeaders := map[string]string{"X-API-Token": *created.APIToken}
	me := testutil.Do(t, r, "GET", "/api/v1/auth/me", tokenHeaders)
	if me.Code != 200 {
		t.Fatalf("API token 认证失败 status=%d", me.Code)
	}

	// 重复用户名 409
	dup := doJSON(t, r, "POST", "/api/v1/users",
		dto.UserCreate{Username: "newbie", Password: "secret1", DisplayName: "重复", Role: "READ_ONLY"}, admin)
	if dup.Code != 409 {
		t.Fatalf("duplicate status=%d body=%s", dup.Code, dup.Body.String())
	}
	var dupBody map[string]any
	_ = json.Unmarshal(dup.Body.Bytes(), &dupBody)
	if dupBody["code"] != "DUPLICATE_USERNAME" || dupBody["message"] != "用户名已存在" {
		t.Fatalf("body=%s", dup.Body.String())
	}

	// 更新（带版本）
	update := doJSON(t, r, "PATCH", "/api/v1/users/5",
		map[string]any{"display_name": "新名字", "version": 1}, admin)
	if update.Code != 200 {
		t.Fatalf("update status=%d body=%s", update.Code, update.Body.String())
	}
	// 版本冲突
	conflict := doJSON(t, r, "PATCH", "/api/v1/users/5",
		map[string]any{"display_name": "x", "version": 1}, admin)
	if conflict.Code != 409 {
		t.Fatalf("version conflict status=%d body=%s", conflict.Code, conflict.Body.String())
	}
	var conflictBody map[string]any
	_ = json.Unmarshal(conflict.Body.Bytes(), &conflictBody)
	if conflictBody["code"] != "VERSION_CONFLICT" {
		t.Fatalf("body=%s", conflict.Body.String())
	}

	// 重新生成令牌（版本需为 2）
	regenerate := doJSON(t, r, "POST", "/api/v1/users/5/api-token/regenerate",
		map[string]any{"version": 2}, admin)
	if regenerate.Code != 200 {
		t.Fatalf("regenerate status=%d body=%s", regenerate.Code, regenerate.Body.String())
	}

	// 删除自己 -> 409
	selfDelete := doJSON(t, r, "DELETE", "/api/v1/users/1", nil, admin)
	if selfDelete.Code != 409 {
		t.Fatalf("self delete status=%d body=%s", selfDelete.Code, selfDelete.Body.String())
	}
	// 删除他人 -> 204
	del := doJSON(t, r, "DELETE", "/api/v1/users/5", nil, admin)
	if del.Code != 204 {
		t.Fatalf("delete status=%d body=%s", del.Code, del.Body.String())
	}
}

func TestRoleGuard(t *testing.T) {
	r := newTestEngine(t)
	readonly := login(t, r, "readonly")
	// 只读用户访问用户管理 -> 403
	w := testutil.Do(t, r, "GET", "/api/v1/users", readonly)
	if w.Code != 403 {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["code"] != "FORBIDDEN" || body["message"] != "没有执行此操作的权限" {
		t.Fatalf("body=%s", w.Body.String())
	}
}

func TestInvalidToken(t *testing.T) {
	r := newTestEngine(t)
	w := testutil.Do(t, r, "GET", "/api/v1/auth/me", map[string]string{"Authorization": "Bearer garbage.token.here"})
	if w.Code != 401 {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["code"] != "INVALID_TOKEN" {
		t.Fatalf("body=%s", w.Body.String())
	}
}
