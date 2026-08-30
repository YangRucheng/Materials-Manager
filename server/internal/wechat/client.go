// Package wechat 微信开放接口客户端（jscode2session / access_token 缓存 / getwxacodeunlimit）。
package wechat

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sync"
	"time"
)

const (
	baseURL      = "https://api.weixin.qq.com"
	codeTimeout  = 10 * time.Second
	tokenTimeout = 5 * time.Second
)

// Client 微信客户端。
type Client struct {
	http *http.Client
	mu   sync.Mutex
	// accessToken 缓存：key = appID
	accessTokens map[string]*tokenEntry
}

type tokenEntry struct {
	value     string
	expiresAt time.Time
}

// New 创建客户端。
func New() *Client {
	return &Client{
		http:         &http.Client{Timeout: 15 * time.Second},
		accessTokens: map[string]*tokenEntry{},
	}
}

// Code2Session 通过 wx.login 的 code 换取 openid/session_key。
func (c *Client) Code2Session(appID, appSecret, code string) (openid, sessionKey string, err error) {
	params := url.Values{}
	params.Set("appid", appID)
	params.Set("secret", appSecret)
	params.Set("js_code", code)
	params.Set("grant_type", "authorization_code")
	client := &http.Client{Timeout: codeTimeout}
	resp, err := client.Get(baseURL + "/sns/jscode2session?" + params.Encode())
	if err != nil {
		return "", "", err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result struct {
		OpenID     string `json:"openid"`
		SessionKey string `json:"session_key"`
		ErrCode    int    `json:"errcode"`
		ErrMsg     string `json:"errmsg"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return "", "", fmt.Errorf("jscode2session 响应解析失败")
	}
	if result.ErrCode != 0 {
		return "", "", fmt.Errorf("wechat errcode=%d %s", result.ErrCode, result.ErrMsg)
	}
	return result.OpenID, result.SessionKey, nil
}

// GetAccessToken 获取小程序 access_token（进程内存缓存，expires_in-300s 提前过期）。
func (c *Client) GetAccessToken(appID, appSecret string) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if entry, ok := c.accessTokens[appID]; ok && time.Now().Before(entry.expiresAt) {
		return entry.value, nil
	}
	params := url.Values{}
	params.Set("grant_type", "client_credential")
	params.Set("appid", appID)
	params.Set("secret", appSecret)
	client := &http.Client{Timeout: tokenTimeout}
	resp, err := client.Get(baseURL + "/cgi-bin/token?" + params.Encode())
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result struct {
		AccessToken string `json:"access_token"`
		ExpiresIn   int    `json:"expires_in"`
		ErrCode     int    `json:"errcode"`
		ErrMsg      string `json:"errmsg"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return "", fmt.Errorf("cgi-bin/token 响应解析失败")
	}
	if result.AccessToken == "" || result.ErrCode != 0 {
		return "", fmt.Errorf("wechat token errcode=%d %s", result.ErrCode, result.ErrMsg)
	}
	expires := result.ExpiresIn - 300
	if expires < 60 {
		expires = 60
	}
	c.accessTokens[appID] = &tokenEntry{
		value: result.AccessToken, expiresAt: time.Now().Add(time.Duration(expires) * time.Second),
	}
	return result.AccessToken, nil
}

// GenerateUnlimitedMaterialCode 生成小程序码（getwxacodeunlimit）。
func (c *Client) GenerateUnlimitedMaterialCode(appID, appSecret, accessToken, scene, envVersion string) ([]byte, string, error) {
	payload := map[string]any{
		"scene":       scene,
		"page":        "pages/outbound/outbound",
		"check_path":  false,
		"env_version": envVersion,
		"width":       430,
	}
	body, _ := json.Marshal(payload)
	client := &http.Client{Timeout: codeTimeout}
	req, err := http.NewRequest("POST", baseURL+"/wxa/getwxacodeunlimit?access_token="+accessToken, bytes.NewReader(body))
	if err != nil {
		return nil, "", err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return nil, "", err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	contentType := resp.Header.Get("Content-Type")
	if len(data) > 0 && data[0] != '{' && (len(contentType) < 5 || contentType[:5] == "image") {
		return data, contentType, nil
	}
	// 错误 JSON
	var errResp struct {
		ErrCode int    `json:"errcode"`
		ErrMsg  string `json:"errmsg"`
	}
	_ = json.Unmarshal(data, &errResp)
	return nil, "", fmt.Errorf("wechat code errcode=%d %s", errResp.ErrCode, errResp.ErrMsg)
}
