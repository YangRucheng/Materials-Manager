package test

import (
	"encoding/json"
	"fmt"
	"testing"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/test/testutil"
)

func TestMiniProgramUsersManagement(t *testing.T) {
	cfg := testutil.NewTestConfig(t)
	db := testutil.OpenTestDB(t, cfg)
	testutil.SeedUsers(t, db)
	u1 := models.MiniProgramUser{DisplayName: "张三", DepartmentName: "电气车间", Enabled: true}
	u2 := models.MiniProgramUser{DisplayName: "张三", DepartmentName: "电气车间", Enabled: true}
	db.Create(&u1)
	db.Create(&u2)
	db.Create(&models.MiniProgramIdentity{MiniProgramUserID: u1.ID, AppID: "wx-a", WechatOpenid: "openid-1"})
	db.Create(&models.MiniProgramIdentity{MiniProgramUserID: u2.ID, AppID: "wx-b", WechatOpenid: "openid-2"})
	r2 := testutil.TestServer(t, cfg, db)
	admin := login(t, r2, "admin")

	// 列表
	list := testutil.Do(t, r2, "GET", "/api/v1/mini-program-users", admin)
	if list.Code != 200 {
		t.Fatalf("list status=%d body=%s", list.Code, list.Body.String())
	}
	var page map[string]any
	_ = json.Unmarshal(list.Body.Bytes(), &page)
	if int(page["total"].(float64)) != 2 {
		t.Fatalf("total=%v", page["total"])
	}

	// 更新
	update := doJSON(t, r2, "PATCH", fmt.Sprintf("/api/v1/mini-program-users/%d", u1.ID),
		map[string]any{"enabled": false, "version": 1}, admin)
	if update.Code != 200 {
		t.Fatalf("update status=%d body=%s", update.Code, update.Body.String())
	}

	// 合并 u2 到 u1
	merge := doJSON(t, r2, "POST", fmt.Sprintf("/api/v1/mini-program-users/%d/merge", u1.ID),
		map[string]any{"source_user_id": u2.ID, "target_version": 2, "source_version": 1}, admin)
	if merge.Code != 200 {
		t.Fatalf("merge status=%d body=%s", merge.Code, merge.Body.String())
	}
	// 合并后源账号删除，目标拥有两个身份
	var merged models.MiniProgramUser
	db.Preload("Identities").First(&merged, u1.ID)
	if len(merged.Identities) != 2 {
		t.Fatalf("合并后身份数=%d", len(merged.Identities))
	}
	var sourceCount int64
	db.Model(&models.MiniProgramUser{}).Where("id = ?", u2.ID).Count(&sourceCount)
	if sourceCount != 0 {
		t.Fatal("源账号应被删除")
	}

	// 删除目标
	del := testutil.Do(t, r2, "DELETE", fmt.Sprintf("/api/v1/mini-program-users/%d", u1.ID), admin)
	if del.Code != 204 {
		t.Fatalf("delete status=%d body=%s", del.Code, del.Body.String())
	}
}

var _ = gorm.DB{}
var _ = gin.Mode
