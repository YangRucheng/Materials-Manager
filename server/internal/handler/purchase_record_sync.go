package handler

import (
	"net/http"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// PurchaseRecordSyncHandler 申购记录同步。
type PurchaseRecordSyncHandler struct {
	App *App
}

func NewPurchaseRecordSyncHandler(app *App) *PurchaseRecordSyncHandler {
	return &PurchaseRecordSyncHandler{App: app}
}

// Targets GET /purchase-record-sync/targets
func (h *PurchaseRecordSyncHandler) Targets(c *gin.Context) {
	limit, appErr := binding.QueryInt(c, "limit", 50, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	cursor, appErr := binding.QueryInt(c, "cursor", 0, 0, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	fields := c.Query("fields")
	minPO := c.Query("min_purchase_order_no")
	items, hasMore, nextCursor, appErr := service.ListSyncTargets(h.App.DB, limit, cursor, fields, minPO)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, dto.PurchaseRecordSyncTargetsRead{
		Items: items, HasMore: hasMore, NextCursor: nextCursor,
	})
}

// Trace POST /purchase-record-sync/trace/{trace_no}
func (h *PurchaseRecordSyncHandler) Trace(c *gin.Context) {
	traceNo := c.Param("trace_no")
	var req dto.PurchaseRecordSyncTraceUpdate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	result, appErr := service.ApplyTraceSync(h.App.DB, traceNo, &req)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, result)
}

// RegisterPurchaseRecordSync 注册 /purchase-record-sync 路由。
func RegisterPurchaseRecordSync(r *gin.RouterGroup, app *App) {
	h := NewPurchaseRecordSyncHandler(app)
	group := r.Group("/purchase-record-sync", auth.AuthManagement(app.Cfg, app.DB), auth.PurchaseWriter())
	group.GET("/targets", h.Targets)
	group.POST("/trace/:trace_no", h.Trace)
}

var _ = strconv.Itoa
var _ = strings.TrimSpace
var _ = models.PurchaseRequestLine{}
