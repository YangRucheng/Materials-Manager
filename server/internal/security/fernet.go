package security

import (
	"crypto/sha256"
	"encoding/base64"
	"fmt"

	"github.com/fernet/fernet-go"
)

// FernetKey 从 APP_FERNET_KEY（优先）或 APP_JWT_SECRET 派生 32 字节并 base64url 编码。
// 与 Python app/services/common.py 的 fernet() 一致。
func FernetKey(fernetKey, jwtSecret string) string {
	if fernetKey != "" {
		digest := sha256.Sum256([]byte(fernetKey))
		return base64.URLEncoding.EncodeToString(digest[:])
	}
	digest := sha256.Sum256([]byte(jwtSecret))
	return base64.URLEncoding.EncodeToString(digest[:])
}

// FernetEncrypt 用独立密钥（APP_FERNET_KEY）加密；密钥为空时回退 jwt_secret 派生。
func FernetEncrypt(fernetKey, jwtSecret, plaintext string) (string, error) {
	keyString := FernetKey(fernetKey, jwtSecret)
	keys, err := fernet.DecodeKeys(keyString)
	if err != nil {
		return "", fmt.Errorf("无效的 Fernet 密钥: %w", err)
	}
	token, err := fernet.EncryptAndSign([]byte(plaintext), keys[0])
	if err != nil {
		return "", err
	}
	return string(token), nil
}

// FernetDecrypt 解密；独立密钥优先，失败后回退 jwt_secret 派生密钥（兼容既有密文）。
func FernetDecrypt(fernetKey, jwtSecret, token string) (string, error) {
	keyStrings := []string{FernetKey(fernetKey, jwtSecret)}
	if fernetKey != "" {
		keyStrings = append(keyStrings, FernetKey("", jwtSecret))
	}
	for _, keyString := range keyStrings {
		keys, err := fernet.DecodeKeys(keyString)
		if err != nil {
			continue
		}
		if msg := fernet.VerifyAndDecrypt([]byte(token), 0, keys); msg != nil {
			return string(msg), nil
		}
	}
	return "", fmt.Errorf("fernet 解密失败")
}
