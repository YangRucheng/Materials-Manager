package webhook

import (
	"testing"
)

// 与 Python hmac 实现交叉验证（固定 timestamp/secret）。
func TestSignersMatchPython(t *testing.T) {
	secret := "secret-123"
	timestamp := "1788008512"

	// 飞书：key=timestamp\nsecret，msg=空
	expectedFeishu := "DwmEw3HB2yXVDKrJaq3N53K0Ydq4huz175gDPXUzLsQ="
	if got := feishuSign(secret, timestamp); got != expectedFeishu {
		t.Fatalf("飞书签名不符: got=%s want=%s", got, expectedFeishu)
	}

	// 钉钉：key=secret，msg=timestamp\nsecret
	expectedDingtalk := "wl5M8G5o3V5eKKzrFDgSpXqXHhXwhrqsq8cw2tVJF2g="
	if got := dingtalkSign(secret, timestamp); got != expectedDingtalk {
		t.Fatalf("钉钉签名不符: got=%s want=%s", got, expectedDingtalk)
	}
}
