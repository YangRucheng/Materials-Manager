package auth

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/middleware"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

// MiniUserKey 上下文中存储的当前小程序用户键。
const MiniUserKey = "auth_mini_user"

// CurrentMiniUser 读取当前小程序用户。
func CurrentMiniUser(c *gin.Context) *models.MiniProgramUser {
	if v, ok := c.Get(MiniUserKey); ok {
		if user, ok := v.(*models.MiniProgramUser); ok {
			return user
		}
	}
	return nil
}

// AuthMiniProgram 小程序访问令牌鉴权（token_type=mini_program）。
func AuthMiniProgram(cfg *config.Config, db *gorm.DB) gin.HandlerFunc {
	return func(c *gin.Context) {
		rawToken, ok := bearerCredentials(c)
		if !ok {
			respond.Error(c, apperrors.New("UNAUTHORIZED", "请先完成微信登录", http.StatusUnauthorized, nil))
			c.Abort()
			return
		}
		claims, err := security.DecodeToken(cfg.JWTSecret, cfg.JWTAlgorithm, rawToken)
		if err != nil || claims.TokenType != security.TokenTypeMiniProgram {
			respond.Error(c, apperrors.New("INVALID_TOKEN", "登录凭证无效或已过期", http.StatusUnauthorized, nil))
			c.Abort()
			return
		}
		userID, convErr := strconv.ParseInt(claims.Subject, 10, 64)
		if convErr != nil || userID <= 0 {
			respond.Error(c, apperrors.New("INVALID_TOKEN", "登录凭证无效或已过期", http.StatusUnauthorized, nil))
			c.Abort()
			return
		}
		var user models.MiniProgramUser
		if err := db.First(&user, userID).Error; err != nil {
			respond.Error(c, apperrors.New("INVALID_TOKEN", "登录凭证无效或已过期", http.StatusUnauthorized, nil))
			c.Abort()
			return
		}
		if !user.Enabled {
			respond.Error(c, apperrors.New("ACCOUNT_DISABLED", "您的账号待审核，请联系管理员", http.StatusForbidden, nil))
			c.Abort()
			return
		}
		c.Set(MiniUserKey, &user)
		c.Set("mini_program_user_id", user.ID)
		middleware.SetUsername(c, "mini:"+strconv.FormatInt(user.ID, 10))
		c.Next()
	}
}

// MiniRegistrationOpenID 小程序注册令牌（token_type=mini_program_registration）→ (app_id, openid)。
func MiniRegistrationOpenID(cfg *config.Config, c *gin.Context) (string, string, bool) {
	rawToken, ok := bearerCredentials(c)
	if !ok {
		respond.Error(c, apperrors.New("UNAUTHORIZED", "请先完成微信登录", http.StatusUnauthorized, nil))
		return "", "", false
	}
	claims, err := security.DecodeToken(cfg.JWTSecret, cfg.JWTAlgorithm, rawToken)
	if err != nil || claims.TokenType != security.TokenTypeMiniProgramRegistration {
		respond.Error(c, apperrors.New("INVALID_TOKEN", "注册凭证无效或已过期", http.StatusUnauthorized, nil))
		return "", "", false
	}
	if claims.Subject == "" || claims.AppID == "" {
		respond.Error(c, apperrors.New("INVALID_TOKEN", "注册凭证无效或已过期", http.StatusUnauthorized, nil))
		return "", "", false
	}
	return claims.AppID, claims.Subject, true
}
