package test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"mime/multipart"
	"net/http/httptest"
	"net/textproto"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

// makePNG 生成指定宽高的纯色 PNG 字节。
func makePNG(t *testing.T, w, h int) []byte {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			img.Set(x, y, color.RGBA{R: 200, G: 100, B: 50, A: 255})
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func uploadImage(t *testing.T, r *gin.Engine, headers map[string]string, filename string, contentType string, data []byte) *httptest.ResponseRecorder {
	t.Helper()
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	h := make(textproto.MIMEHeader)
	h.Set("Content-Disposition", fmt.Sprintf(`form-data; name="file"; filename="%s"`, filename))
	if contentType != "" {
		h.Set("Content-Type", contentType)
	}
	part, err := writer.CreatePart(h)
	if err != nil {
		t.Fatal(err)
	}
	_, _ = part.Write(data)
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest("POST", "/api/v1/files/images", &body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func TestUploadAndReadImage(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	pngBytes := makePNG(t, 64, 48)
	w := uploadImage(t, r, warehouse, "test.png", "image/png", pngBytes)
	if w.Code != 201 {
		t.Fatalf("upload status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["mime_type"] != "image/png" {
		t.Fatalf("mime_type=%v", body["mime_type"])
	}
	if int(body["width"].(float64)) != 64 || int(body["height"].(float64)) != 48 {
		t.Fatalf("尺寸错误: %v", body)
	}
	fileID := body["id"].(string)

	// 匿名读取原图
	read := testutil.Do(t, r, "GET", "/api/v1/files/images/"+fileID, nil)
	if read.Code != 200 {
		t.Fatalf("read status=%d body=%s", read.Code, read.Body.String())
	}
	if read.Header().Get("Content-Type") != "image/png" {
		t.Fatalf("Content-Type=%q", read.Header().Get("Content-Type"))
	}
	// 服务端会重新编码 PNG（压缩优化），校验解码后尺寸一致
	decoded, _, err := image.Decode(bytes.NewReader(read.Body.Bytes()))
	if err != nil {
		t.Fatalf("服务端图片无法解码: %v", err)
	}
	if decoded.Bounds().Dx() != 64 || decoded.Bounds().Dy() != 48 {
		t.Fatalf("服务端图片尺寸错误: %v", decoded.Bounds())
	}

	// 预览
	preview := testutil.Do(t, r, "GET", "/api/v1/files/images/"+fileID+"?size=32", nil)
	if preview.Code != 200 {
		t.Fatalf("preview status=%d", preview.Code)
	}
	if preview.Header().Get("Content-Type") != "image/webp" {
		t.Fatalf("preview Content-Type=%q", preview.Header().Get("Content-Type"))
	}
	if len(preview.Body.Bytes()) == 0 {
		t.Fatal("preview 为空")
	}
}

func TestUploadRejectsWrongType(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	w := uploadImage(t, r, warehouse, "doc.txt", "text/plain", []byte("not an image"))
	if w.Code != 400 {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if body["code"] != "INVALID_IMAGE_TYPE" {
		t.Fatalf("code=%v", body["code"])
	}
}

func TestUploadDedup(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	pngBytes := makePNG(t, 20, 20)
	first := uploadImage(t, r, warehouse, "a.png", "image/png", pngBytes)
	second := uploadImage(t, r, warehouse, "b.png", "image/png", pngBytes)
	if first.Code != 201 || second.Code != 201 {
		t.Fatalf("status=%d/%d", first.Code, second.Code)
	}
	var a, b map[string]any
	_ = json.Unmarshal(first.Body.Bytes(), &a)
	_ = json.Unmarshal(second.Body.Bytes(), &b)
	if a["id"] != b["id"] {
		t.Fatalf("相同内容应去重: %v vs %v", a["id"], b["id"])
	}
}

func TestUploadRequiresAuth(t *testing.T) {
	r := newTestEngine(t)
	w := uploadImage(t, r, nil, "a.png", "image/png", makePNG(t, 10, 10))
	if w.Code != 401 {
		t.Fatalf("匿名上传应 401, status=%d", w.Code)
	}
}

func TestImageInUseCannotDelete(t *testing.T) {
	r := newTestEngine(t)
	warehouse := login(t, r, "warehouse")
	pngBytes := makePNG(t, 30, 30)
	upload := uploadImage(t, r, warehouse, "a.png", "image/png", pngBytes)
	var up map[string]any
	_ = json.Unmarshal(upload.Body.Bytes(), &up)
	fileID := up["id"].(string)
	// 引用到物资
	create := doJSON(t, r, "POST", "/api/v1/stock-materials",
		map[string]any{"name": "带图物资", "model_spec": "M1", "unit_name": "个", "image_ids": []any{fileID}}, warehouse)
	if create.Code != 201 {
		t.Fatalf("create with image status=%d body=%s", create.Code, create.Body.String())
	}
	// 删除被引用图片 -> 409
	del := testutil.Do(t, r, "DELETE", "/api/v1/files/images/"+fileID, warehouse)
	if del.Code != 409 {
		t.Fatalf("delete in-use status=%d body=%s", del.Code, del.Body.String())
	}
	var body map[string]any
	_ = json.Unmarshal(del.Body.Bytes(), &body)
	if body["code"] != "FILE_IN_USE" {
		t.Fatalf("code=%v", body["code"])
	}
}

func TestOrphanReportAndCleanup(t *testing.T) {
	r := newTestEngine(t)
	admin := login(t, r, "admin")
	warehouse := login(t, r, "warehouse")
	// 上传但未引用 -> 孤儿
	upload := uploadImage(t, r, warehouse, "orphan.png", "image/png", makePNG(t, 15, 15))
	var up map[string]any
	_ = json.Unmarshal(upload.Body.Bytes(), &up)
	fileID := up["id"].(string)
	// 引用一张 -> 非孤儿
	upload2 := uploadImage(t, r, warehouse, "used.png", "image/png", makePNG(t, 18, 18))
	var up2 map[string]any
	_ = json.Unmarshal(upload2.Body.Bytes(), &up2)
	usedID := up2["id"].(string)
	create := doJSON(t, r, "POST", "/api/v1/stock-materials",
		map[string]any{"name": "引用图物资", "model_spec": "M2", "unit_name": "个", "image_ids": []any{usedID}}, warehouse)
	if create.Code != 201 {
		t.Fatalf("create status=%d", create.Code)
	}

	report := testutil.Do(t, r, "GET", "/api/v1/files/images/orphans?older_than_hours=0", admin)
	if report.Code != 200 {
		t.Fatalf("orphan report status=%d body=%s", report.Code, report.Body.String())
	}
	var rep map[string]any
	_ = json.Unmarshal(report.Body.Bytes(), &rep)
	records := rep["unreferenced_records"].([]any)
	found := false
	for _, rec := range records {
		if rec.(map[string]any)["id"] == fileID {
			found = true
		}
		if rec.(map[string]any)["id"] == usedID {
			t.Fatal("被引用图片不应出现在孤儿列表")
		}
	}
	if !found {
		t.Fatalf("孤儿应包含 %s: %v", fileID, records)
	}

	// 清理孤儿
	cleanup := testutil.Do(t, r, "DELETE", "/api/v1/files/images/orphans?older_than_hours=0", admin)
	if cleanup.Code != 200 {
		t.Fatalf("cleanup status=%d body=%s", cleanup.Code, cleanup.Body.String())
	}
	var clean map[string]any
	_ = json.Unmarshal(cleanup.Body.Bytes(), &clean)
	deleted := clean["deleted_record_ids"].([]any)
	if len(deleted) == 0 {
		t.Fatal("应清理至少一个孤儿记录")
	}
	// 孤儿图片已不可读
	read := testutil.Do(t, r, "GET", "/api/v1/files/images/"+fileID, nil)
	if read.Code != 400 {
		t.Fatalf("已清理图片应 400, status=%d", read.Code)
	}
}

var _ = gin.Mode
