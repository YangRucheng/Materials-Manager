// Package dto 定义请求/响应数据结构（与 docs/openapi.yaml 契约一致）。
// 字段名 snake_case；可空字段输出 null（不加 omitempty）。
package dto

import (
	"github.com/yangrucheng/materials-manager/server/internal/models"
)

// ============ 认证 ============

type LoginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required,min=1,max=128"`
}

type LoginResponse struct {
	AccessToken  string   `json:"access_token"`
	RefreshToken string   `json:"refresh_token"`
	TokenType    string   `json:"token_type"`
	User         UserRead `json:"user"`
}

type RefreshTokenRequest struct {
	RefreshToken string `json:"refresh_token" binding:"required,min=1,max=4096"`
}

type TokenPairResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	TokenType    string `json:"token_type"`
}

// ============ 用户 ============

type UserRead struct {
	ID          int64  `json:"id"`
	Username    string `json:"username"`
	DisplayName string `json:"display_name"`
	Role        string `json:"role"`
	Enabled     bool   `json:"enabled"`
	Version     int    `json:"version"`
}

func NewUserRead(u *models.User) UserRead {
	return UserRead{
		ID:          u.ID,
		Username:    u.Username,
		DisplayName: u.DisplayName,
		Role:        u.Role,
		Enabled:     u.Enabled,
		Version:     u.Version,
	}
}

type UserApiTokenRead struct {
	UserRead
	// api_token 仅在新建/重新生成接口返回一次明文；列表读取为 null。
	APIToken *string `json:"api_token"`
}

func NewUserApiTokenRead(u *models.User) UserApiTokenRead {
	out := UserApiTokenRead{UserRead: NewUserRead(u)}
	if u.APIToken != "" {
		token := u.APIToken
		out.APIToken = &token
	}
	return out
}

type UserCreate struct {
	Username    string `json:"username" binding:"required,min=3,max=64"`
	Password    string `json:"password" binding:"required,min=6,max=128"`
	DisplayName string `json:"display_name" binding:"required,min=1,max=128"`
	Role        string `json:"role" binding:"required,oneof=SUPER_ADMIN WAREHOUSE_ADMIN PURCHASE_ADMIN READ_ONLY"`
	Enabled     *bool  `json:"enabled"`
}

type UserUpdate struct {
	Username    *string `json:"username" binding:"omitempty,min=3,max=64"`
	DisplayName *string `json:"display_name" binding:"omitempty,min=1,max=128"`
	Password    *string `json:"password" binding:"omitempty,min=6,max=128"`
	Role        *string `json:"role" binding:"omitempty,oneof=SUPER_ADMIN WAREHOUSE_ADMIN PURCHASE_ADMIN READ_ONLY"`
	Enabled     *bool   `json:"enabled"`
	Version     int     `json:"version" binding:"required"`
}

type UserApiTokenRegenerate struct {
	Version int `json:"version" binding:"required"`
}

// ============ 分页 ============

type Page[T any] struct {
	Items    []T `json:"items"`
	Page     int `json:"page"`
	PageSize int `json:"page_size"`
	Total    int `json:"total"`
}
