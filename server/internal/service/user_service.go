// Package service 实现业务逻辑（等价 backend/app/services/*.py）。
package service

import (
	"errors"
	"net/http"
	"strconv"

	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/config"
	"github.com/yangrucheng/materials-manager/server/internal/database"
	apperrors "github.com/yangrucheng/materials-manager/server/internal/errors"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/security"
)

// ============ 通用 ============

// ValidateVersion 乐观锁版本校验（expected 为 0 或未提供时不校验，等价 Python）。
func ValidateVersion(expected, actual int) *apperrors.AppError {
	if expected != 0 && expected != actual {
		return apperrors.VersionConflict(expected, actual)
	}
	return nil
}

// 校验版本：expected 用指针，nil 表示未提供。
func validateVersionPtr(expected *int, actual int) *apperrors.AppError {
	if expected == nil {
		return nil
	}
	return ValidateVersion(*expected, actual)
}

// IsNotFound 判断 GORM 记录不存在。
func IsNotFound(err error) bool { return errors.Is(err, gorm.ErrRecordNotFound) }

// DatabaseError 包装数据库错误为统一错误码（调用方按需覆盖）。
func DatabaseError(err error) *apperrors.AppError {
	return database.MapDBError(err)
}

// ============ 认证 ============

// Login 用户名密码登录；失败统一 401 INVALID_CREDENTIALS。
func Login(cfg *config.Config, db *gorm.DB, username, password string) (*models.User, string, string, *apperrors.AppError) {
	var user models.User
	err := db.Where("username = ?", username).First(&user).Error
	if IsNotFound(err) {
		return nil, "", "", invalidCredentials()
	}
	if err != nil {
		return nil, "", "", DatabaseError(err)
	}
	if !user.Enabled || !security.VerifyPassword(user.PasswordHash, password) {
		return nil, "", "", invalidCredentials()
	}
	access, err := security.NewAccessToken(cfg.JWTSecret, cfg.JWTAlgorithm, user.ID, cfg.TokenExpireAccess())
	if err != nil {
		return nil, "", "", apperrors.New("INTERNAL_SERVER_ERROR", "令牌生成失败", 500, nil)
	}
	refresh, err := security.NewRefreshToken(cfg.JWTSecret, cfg.JWTAlgorithm, user.ID, user.Version, cfg.TokenExpireRefresh())
	if err != nil {
		return nil, "", "", apperrors.New("INTERNAL_SERVER_ERROR", "令牌生成失败", 500, nil)
	}
	return &user, access, refresh, nil
}

func invalidCredentials() *apperrors.AppError {
	return apperrors.New("INVALID_CREDENTIALS", "用户名或密码错误", http.StatusUnauthorized, nil)
}

// Refresh 刷新令牌；校验 token_type=management_refresh 与用户 version。
func Refresh(cfg *config.Config, db *gorm.DB, refreshToken string) (string, string, *apperrors.AppError) {
	claims, err := security.DecodeToken(cfg.JWTSecret, cfg.JWTAlgorithm, refreshToken)
	if err != nil || claims.TokenType != "management_refresh" {
		return "", "", invalidRefreshToken()
	}
	userID, convErr := strconv.ParseInt(claims.Subject, 10, 64)
	tokenVersion := 0
	if claims.Version != nil {
		tokenVersion = *claims.Version
	}
	if convErr != nil || userID <= 0 {
		return "", "", invalidRefreshToken()
	}
	var user models.User
	err = db.First(&user, userID).Error
	if IsNotFound(err) || (err == nil && (!user.Enabled || user.Version != tokenVersion)) {
		return "", "", invalidRefreshToken()
	}
	if err != nil {
		return "", "", DatabaseError(err)
	}
	access, err := security.NewAccessToken(cfg.JWTSecret, cfg.JWTAlgorithm, user.ID, cfg.TokenExpireAccess())
	if err != nil {
		return "", "", apperrors.New("INTERNAL_SERVER_ERROR", "令牌生成失败", 500, nil)
	}
	newRefresh, err := security.NewRefreshToken(cfg.JWTSecret, cfg.JWTAlgorithm, user.ID, user.Version, cfg.TokenExpireRefresh())
	if err != nil {
		return "", "", apperrors.New("INTERNAL_SERVER_ERROR", "令牌生成失败", 500, nil)
	}
	return access, newRefresh, nil
}

func invalidRefreshToken() *apperrors.AppError {
	return apperrors.New("INVALID_REFRESH_TOKEN", "续期凭证无效或已过期", http.StatusUnauthorized, nil)
}

// ============ 用户管理 ============

// ListUsers 分页 + keyword（username/display_name LIKE）。
func ListUsers(db *gorm.DB, keyword string, page, pageSize int) ([]models.User, int, *apperrors.AppError) {
	q := db.Model(&models.User{})
	if keyword != "" {
		like := "%" + keyword + "%"
		q = q.Where("username LIKE ? OR display_name LIKE ?", like, like)
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	var items []models.User
	if err := q.Order("id").Offset((page - 1) * pageSize).Limit(pageSize).Find(&items).Error; err != nil {
		return nil, 0, DatabaseError(err)
	}
	return items, int(total), nil
}

// CreateUser 创建用户并签发一次性的接口令牌明文。
func CreateUser(db *gorm.DB, username, password, displayName, role string, enabled bool) (*models.User, *apperrors.AppError) {
	hash, err := security.HashPassword(password)
	if err != nil {
		return nil, apperrors.New("INTERNAL_SERVER_ERROR", "密码加密失败", 500, nil)
	}
	user := models.User{
		Username:     username,
		PasswordHash: hash,
		DisplayName:  displayName,
		Role:         role,
		Enabled:      enabled,
	}
	issueAPIToken(&user)
	if err := db.Create(&user).Error; err != nil {
		if database.IsDuplicateError(err) {
			return nil, apperrors.New("DUPLICATE_USERNAME", "用户名已存在", http.StatusConflict, nil)
		}
		return nil, DatabaseError(err)
	}
	return &user, nil
}

// UpdateUser 更新用户字段（乐观锁 + 可选改密）。
func UpdateUser(db *gorm.DB, itemID int64, username, displayName *string, password *string, role *string, enabled *bool, version int) (*models.User, *apperrors.AppError) {
	var user models.User
	if err := db.First(&user, itemID).Error; err != nil {
		if IsNotFound(err) {
			return nil, apperrors.NotFound("用户")
		}
		return nil, DatabaseError(err)
	}
	if appErr := ValidateVersion(version, user.Version); appErr != nil {
		return nil, appErr
	}
	updates := map[string]any{}
	if username != nil {
		updates["username"] = *username
	}
	if displayName != nil {
		updates["display_name"] = *displayName
	}
	if role != nil {
		updates["role"] = *role
	}
	if enabled != nil {
		updates["enabled"] = *enabled
	}
	if password != nil && *password != "" {
		hash, err := security.HashPassword(*password)
		if err != nil {
			return nil, apperrors.New("INTERNAL_SERVER_ERROR", "密码加密失败", 500, nil)
		}
		updates["password_hash"] = hash
	}
	updates["version"] = gorm.Expr("version + 1")
	updates["updated_at"] = models.UTCNow()
	if err := db.Model(&user).Updates(updates).Error; err != nil {
		if database.IsDuplicateError(err) {
			return nil, apperrors.New("DUPLICATE_USERNAME", "用户名已存在", http.StatusConflict, nil)
		}
		return nil, DatabaseError(err)
	}
	if err := db.First(&user, itemID).Error; err != nil {
		return nil, DatabaseError(err)
	}
	return &user, nil
}

// RegenerateAPIToken 重新生成接口令牌（乐观锁）。
func RegenerateAPIToken(db *gorm.DB, itemID int64, version int) (*models.User, *apperrors.AppError) {
	var user models.User
	if err := db.First(&user, itemID).Error; err != nil {
		if IsNotFound(err) {
			return nil, apperrors.NotFound("用户")
		}
		return nil, DatabaseError(err)
	}
	if appErr := ValidateVersion(version, user.Version); appErr != nil {
		return nil, appErr
	}
	issueAPIToken(&user)
	user.Version++
	user.UpdatedAt = models.UTCNow()
	if err := db.Save(&user).Error; err != nil {
		return nil, DatabaseError(err)
	}
	return &user, nil
}

// DeleteUser 删除用户；禁止删除当前登录用户。
func DeleteUser(db *gorm.DB, itemID, currentUserID int64) *apperrors.AppError {
	var user models.User
	if err := db.First(&user, itemID).Error; err != nil {
		if IsNotFound(err) {
			return apperrors.NotFound("用户")
		}
		return DatabaseError(err)
	}
	if user.ID == currentUserID {
		return apperrors.New("CANNOT_DELETE_CURRENT_USER", "不能删除当前登录用户", http.StatusConflict, nil)
	}
	if err := db.Delete(&user).Error; err != nil {
		return DatabaseError(err)
	}
	return nil
}

// issueAPIToken 生成新令牌：库中只存哈希，明文挂到对象上一次性返回。
func issueAPIToken(user *models.User) string {
	token := security.UUID4Hex()
	user.APITokenHash = security.HashAPIToken(token)
	user.APIToken = token
	return token
}
