// Package webhook 提供飞书/钉钉 Webhook 签名（复刻 webhook_service 的 HMAC 细节）。
package webhook

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"time"
)

// Platform 平台。
type Platform int

const (
	PlatformFeishu Platform = iota
	PlatformDingtalk
)

// BuildPayload 构造渠道 payload 与签名 URL：
//   - 飞书：msg_type=text，content.text=title\n\ntext，body 含 timestamp(秒字符串) 与 sign
//   - 钉钉：msgtype=markdown，markdown.title/text，timestamp(毫秒) 与 sign 追加到 URL query
func BuildPayload(platform Platform, webhookURL, secret, title, text string) (payload []byte, signedURL string, err error) {
	switch platform {
	case PlatformFeishu:
		body := map[string]any{
			"msg_type": "text",
			"content":  map[string]string{"text": title + "\n" + text},
		}
		if secret != "" {
			timestamp := itoa64(time.Now().Unix())
			sign := feishuSign(secret, timestamp)
			body["timestamp"] = timestamp
			body["sign"] = sign
		}
		data, err := json.Marshal(body)
		return data, webhookURL, err
	case PlatformDingtalk:
		markdownText := replaceNewlines(text)
		body := map[string]any{
			"msgtype": "markdown",
			"markdown": map[string]string{
				"title": title,
				"text":  "### " + title + "\n\n" + markdownText,
			},
		}
		signedURL := webhookURL
		if secret != "" {
			timestamp := itoa64(time.Now().UnixMilli())
			sign := dingtalkSign(secret, timestamp)
			sep := "?"
			if containsRune(webhookURL, '?') {
				sep = "&"
			}
			signedURL = webhookURL + sep + "timestamp=" + timestamp + "&sign=" + urlQueryEscape(sign)
		}
		data, err := json.Marshal(body)
		return data, signedURL, err
	}
	return nil, "", nil
}

func replaceNewlines(s string) string {
	out := make([]byte, 0, len(s)+16)
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			out = append(out, '\n', '\n')
		} else {
			out = append(out, s[i])
		}
	}
	return string(out)
}

// feishuSign 飞书：HMAC-SHA256(key=timestamp\nsecret, msg=空)。
func feishuSign(secret, timestamp string) string {
	key := timestamp + "\n" + secret
	mac := hmac.New(sha256.New, []byte(key))
	mac.Write([]byte(""))
	return base64.StdEncoding.EncodeToString(mac.Sum(nil))
}

// dingtalkSign 钉钉：HMAC-SHA256(key=secret, msg=timestamp\nsecret)。
func dingtalkSign(secret, timestamp string) string {
	stringToSign := timestamp + "\n" + secret
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(stringToSign))
	return base64.StdEncoding.EncodeToString(mac.Sum(nil))
}

func containsRune(s string, r rune) bool {
	for _, c := range s {
		if c == r {
			return true
		}
	}
	return false
}

func itoa64(v int64) string {
	if v == 0 {
		return "0"
	}
	neg := v < 0
	u := uint64(v)
	if neg {
		u = uint64(-v)
	}
	var buf [20]byte
	i := len(buf)
	for u > 0 {
		i--
		buf[i] = byte('0' + u%10)
		u /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}

func urlQueryEscape(s string) string {
	// 只对签名 base64 字符做必要转义
	var sb []byte
	for i := 0; i < len(s); i++ {
		c := s[i]
		if (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~' {
			sb = append(sb, c)
		} else {
			sb = append(sb, '%', hexChar(c>>4), hexChar(c&0x0f))
		}
	}
	return string(sb)
}

func hexChar(b byte) byte {
	if b < 10 {
		return '0' + b
	}
	return 'A' + (b - 10)
}
