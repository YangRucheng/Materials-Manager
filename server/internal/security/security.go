// Package security 提供与 Python 后端兼容的密码学原语：
// JWT（HS256）、Argon2 口令哈希（兼容 argon2-cffi PHC 格式）、Fernet 加密（兼容 cryptography）、
// 接口令牌（SHA-256 hex）。
package security

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"golang.org/x/crypto/argon2"
)

// ============ 常量（与 Python 一致） ============

const (
	TokenTypeManagementAccess        = "management_access"
	TokenTypeManagementRefresh       = "management_refresh"
	TokenTypeMiniProgram             = "mini_program"
	TokenTypeMiniProgramRegistration = "mini_program_registration"
)

// ============ JWT ============

// Claims 与 Python jwt.encode payload 对齐。
type Claims struct {
	TokenType string `json:"token_type"`
	Version   *int   `json:"version,omitempty"`
	AppID     string `json:"app_id,omitempty"`
	jwt.RegisteredClaims
}

// NewAccessToken 生成管理端访问令牌（sub=user_id, token_type=management_access）。
func NewAccessToken(secret string, algorithm string, userID int64, ttl time.Duration) (string, error) {
	return encodeToken(secret, algorithm, Claims{
		TokenType: TokenTypeManagementAccess,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   fmt.Sprintf("%d", userID),
			IssuedAt:  jwt.NewNumericDate(time.Now().UTC()),
			ExpiresAt: jwt.NewNumericDate(time.Now().UTC().Add(ttl)),
			ID:        uuid.New().String(),
		},
	})
}

// NewRefreshToken 生成管理端刷新令牌（携带 user version 用于吊销校验）。
func NewRefreshToken(secret, algorithm string, userID int64, version int, ttl time.Duration) (string, error) {
	return encodeToken(secret, algorithm, Claims{
		TokenType: TokenTypeManagementRefresh,
		Version:   &version,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   fmt.Sprintf("%d", userID),
			IssuedAt:  jwt.NewNumericDate(time.Now().UTC()),
			ExpiresAt: jwt.NewNumericDate(time.Now().UTC().Add(ttl)),
			ID:        uuid.New().String(),
		},
	})
}

// NewMiniProgramAccessToken 生成小程序访问令牌。
func NewMiniProgramAccessToken(secret, algorithm string, userID int64, ttl time.Duration) (string, error) {
	return encodeToken(secret, algorithm, Claims{
		TokenType: TokenTypeMiniProgram,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   fmt.Sprintf("%d", userID),
			IssuedAt:  jwt.NewNumericDate(time.Now().UTC()),
			ExpiresAt: jwt.NewNumericDate(time.Now().UTC().Add(ttl)),
			ID:        uuid.New().String(),
		},
	})
}

// NewMiniProgramRegistrationToken 生成小程序注册令牌（sub=openid, app_id claim, 10 分钟）。
func NewMiniProgramRegistrationToken(secret, algorithm, appID, openid string, ttl time.Duration) (string, error) {
	return encodeToken(secret, algorithm, Claims{
		TokenType: TokenTypeMiniProgramRegistration,
		AppID:     appID,
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   openid,
			IssuedAt:  jwt.NewNumericDate(time.Now().UTC()),
			ExpiresAt: jwt.NewNumericDate(time.Now().UTC().Add(ttl)),
			ID:        uuid.New().String(),
		},
	})
}

func encodeToken(secret, algorithm string, claims Claims) (string, error) {
	if algorithm == "" {
		algorithm = "HS256"
	}
	return jwt.NewWithClaims(jwt.GetSigningMethod(algorithm), claims).SignedString([]byte(secret))
}

// DecodeToken 校验并解析令牌；返回解析后的 claims。
func DecodeToken(secret, algorithm, tokenString string) (*Claims, error) {
	if algorithm == "" {
		algorithm = "HS256"
	}
	claims := &Claims{}
	_, err := jwt.ParseWithClaims(tokenString, claims, func(t *jwt.Token) (any, error) {
		return []byte(secret), nil
	}, jwt.WithValidMethods([]string{algorithm}))
	if err != nil {
		return nil, err
	}
	return claims, nil
}

// ============ Argon2（兼容 argon2-cffi 默认参数） ============

const (
	argonTime    = 3
	argonMemory  = 64 * 1024 // 64 MiB
	argonThreads = 4
	argonKeyLen  = 32
	argonSaltLen = 16
)

// HashPassword 生成 PHC 格式的 argon2id 哈希（与 argon2-cffi 默认参数一致）。
func HashPassword(password string) (string, error) {
	salt := make([]byte, argonSaltLen)
	if _, err := rand.Read(salt); err != nil {
		return "", err
	}
	key := argon2.IDKey([]byte(password), salt, argonTime, argonMemory, argonThreads, argonKeyLen)
	return fmt.Sprintf("$argon2id$v=%d$m=%d,t=%d,p=%d$%s$%s",
		argon2.Version, argonMemory, argonTime, argonThreads,
		base64.RawStdEncoding.EncodeToString(salt),
		base64.RawStdEncoding.EncodeToString(key)), nil
}

// VerifyPassword 校验口令（从存储哈希解析参数，兼容 argon2-cffi 生成的历史哈希）。
func VerifyPassword(hash, password string) bool {
	parts := strings.Split(hash, "$")
	// ["", "argon2id", "v=19", "m=65536,t=3,p=4", salt, hash]
	if len(parts) != 6 || parts[1] != "argon2id" {
		return false
	}
	var version int
	if _, err := fmt.Sscanf(parts[2], "v=%d", &version); err != nil {
		return false
	}
	var memory uint32
	var timeCost uint32
	var threads uint8
	if _, err := fmt.Sscanf(parts[3], "m=%d,t=%d,p=%d", &memory, &timeCost, &threads); err != nil {
		return false
	}
	salt, err := base64.RawStdEncoding.DecodeString(parts[4])
	if err != nil {
		return false
	}
	expected, err := base64.RawStdEncoding.DecodeString(parts[5])
	if err != nil {
		return false
	}
	if version != argon2.Version {
		return false
	}
	actual := argon2.IDKey([]byte(password), salt, timeCost, memory, threads, uint32(len(expected)))
	return subtleConstantTimeEqual(actual, expected)
}

// subtleConstantTimeEqual 常数时间比较（避免引入额外依赖）。
func subtleConstantTimeEqual(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	var v byte
	for i := range a {
		v |= a[i] ^ b[i]
	}
	return v == 0
}

// ============ API Token ============

// HashAPIToken 计算接口令牌的 SHA-256 hex（与 Python _hash_api_token 一致）。
func HashAPIToken(token string) string {
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:])
}

// UUID4Hex 生成 uuid4 字符串（36 字符，接口令牌格式）。
func UUID4Hex() string {
	return uuid.New().String()
}
