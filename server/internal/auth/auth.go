// Package auth 提供认证与鉴权中间件，复刻 backend/app/core/permissions.py 语义。
package auth

import (
	"errors"
	"net/http"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/middleware"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

// UserKey 上下文中存储的当前用户键。
const UserKey = "auth_user"

// CurrentUser 读取当前管理端用户；未认证时返回 nil。
func CurrentUser(c *gin.Context) *models.User {
	if v, ok := c.Get(UserKey); ok {
		if user, ok := v.(*models.User); ok {
			return user
		}
	}
	return nil
}

// 从 Authorization: Bearer <token> 头提取凭证。
func bearerCredentials(c *gin.Context) (string, bool) {
	authz := strings.TrimSpace(c.GetHeader("Authorization"))
	if authz == "" {
		return "", false
	}
	scheme, rest, found := strings.Cut(authz, " ")
	if !found || !strings.EqualFold(scheme, "Bearer") {
		return "", false
	}
	credential := strings.TrimSpace(rest)
	return credential, credential != ""
}

// findUserByAPIToken 查询接口令牌对应的用户（长度必须为 36，等价 Python 判据）。
func findUserByAPIToken(db *gorm.DB, token string) (*models.User, error) {
	if len(token) != 36 {
		return nil, nil
	}
	var user models.User
	err := db.Where("api_token_hash = ?", security.HashAPIToken(token)).First(&user).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &user, nil
}

func disabledUserError() *apperrors.AppError {
	return apperrors.New("USER_DISABLED", "用户不存在或已停用", http.StatusUnauthorized, nil)
}

func databaseError(err error) *apperrors.AppError {
	return apperrors.New("DATABASE_UNAVAILABLE", "数据库暂时不可用，请稍后重试",
		http.StatusServiceUnavailable, nil)
}

// authenticateManagementUser 复刻 authenticate_management_user 的完整分支。
func authenticateManagementUser(cfg *config.Config, db *gorm.DB, c *gin.Context) (*models.User, *apperrors.AppError) {
	apiTokenHeader := c.GetHeader("X-API-Token")
	if apiTokenHeader != "" {
		user, err := findUserByAPIToken(db, apiTokenHeader)
		if err != nil {
			return nil, databaseError(err)
		}
		if user == nil {
			return nil, apperrors.New("INVALID_TOKEN", "接口令牌无效", http.StatusUnauthorized, nil)
		}
		if !user.Enabled {
			return nil, disabledUserError()
		}
		return user, nil
	}

	rawToken, ok := bearerCredentials(c)
	if !ok {
		return nil, apperrors.New("UNAUTHORIZED", "请先登录", http.StatusUnauthorized, nil)
	}
	// 长度 <= 36 时先按接口令牌尝试（USER_DISABLED 直接上抛，其余回退 JWT）。
	if len(rawToken) <= 36 {
		user, err := findUserByAPIToken(db, rawToken)
		if err == nil && user != nil {
			if !user.Enabled {
				return nil, disabledUserError()
			}
			return user, nil
		}
	}
	claims, err := security.DecodeToken(cfg.JWTSecret, cfg.JWTAlgorithm, rawToken)
	if err != nil {
		return nil, invalidCredentialError()
	}
	if claims.TokenType != "" && claims.TokenType != "management" && claims.TokenType != "management_access" {
		return nil, invalidCredentialError()
	}
	userID, convErr := strconv.ParseInt(claims.Subject, 10, 64)
	if convErr != nil || userID <= 0 {
		return nil, invalidCredentialError()
	}
	var user models.User
	if err := db.First(&user, userID).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, disabledUserError()
		}
		return nil, databaseError(err)
	}
	if !user.Enabled {
		return nil, disabledUserError()
	}
	return &user, nil
}

func invalidCredentialError() *apperrors.AppError {
	return apperrors.New("INVALID_TOKEN", "登录凭证或接口令牌无效", http.StatusUnauthorized, nil)
}

// AuthManagement 管理端认证中间件：把当前用户写入上下文，失败则 401/403 并中断。
func AuthManagement(cfg *config.Config, db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		user, appErr := authenticateManagementUser(cfg, db, c)
		if appErr != nil {
			respond.Error(c, appErr)
			c.Abort()
			return
		}
		c.Set(UserKey, user)
		c.Set("user_id", user.ID)
		middleware.SetUsername(c, user.Username)
		c.Next()
	}
}

// RequireRoles 角色守卫：当前用户角色不在允许集合内 -> 403 FORBIDDEN。
func RequireRoles(roles ...string) gin.HandlerFunc {
	allowed := map[string]bool{}
	for _, r := range roles {
		allowed[r] = true
	}
	return func(c *gin.Context) {
		user := CurrentUser(c)
		if user != nil && allowed[user.Role] {
			c.Next()
			return
		}
		respond.Error(c, apperrors.New("FORBIDDEN", "没有执行此操作的权限",
			http.StatusForbidden, nil))
		c.Abort()
	}
}

// WarehouseWriter = SUPER_ADMIN + WAREHOUSE_ADMIN。
func WarehouseWriter() gin.HandlerFunc {
	return RequireRoles("SUPER_ADMIN", "WAREHOUSE_ADMIN")
}

// PurchaseWriter = SUPER_ADMIN + PURCHASE_ADMIN。
func PurchaseWriter() gin.HandlerFunc {
	return RequireRoles("SUPER_ADMIN", "PURCHASE_ADMIN")
}

// SuperAdmin 仅超级管理员。
func SuperAdmin() gin.HandlerFunc {
	return RequireRoles("SUPER_ADMIN")
}
