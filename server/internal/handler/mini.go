package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/yangrucheng/materials-manager/server/internal/auth"
	"github.com/yangrucheng/materials-manager/server/internal/binding"
	"github.com/yangrucheng/materials-manager/server/internal/dto"
	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/respond"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
	"github.com/yangrucheng/materials-manager/server/internal/service"
)

// MiniHandler 小程序。
type MiniHandler struct {
	App *App
}

func NewMiniHandler(app *App) *MiniHandler { return &MiniHandler{App: app} }

func miniUserRead(u *models.MiniProgramUser) *dto.MiniProgramUserRead {
	identities := make([]dto.MiniProgramIdentityRead, 0, len(u.Identities))
	for _, id := range u.Identities {
		identities = append(identities, dto.MiniProgramIdentityRead{
			ID: id.ID, AppID: id.AppID, WechatOpenid: id.WechatOpenid,
			CreatedAt: serialize.UTCZTime(id.CreatedAt),
		})
	}
	return &dto.MiniProgramUserRead{
		ID: u.ID, DisplayName: u.DisplayName, DepartmentName: u.DepartmentName,
		Enabled: u.Enabled, Identities: identities,
		CreatedAt: serialize.UTCZTime(u.CreatedAt), UpdatedAt: serialize.UTCZTime(u.UpdatedAt),
		Version: u.Version,
	}
}

// WXLogin POST /mini-program/auth/wx-login
func (h *MiniHandler) WXLogin(c *gin.Context) {
	var req struct {
		Code  string `json:"code" binding:"required"`
		AppID string `json:"app_id"`
	}
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	access, _, user, requiresProfile, regToken, appErr := service.WXLogin(h.App.Cfg, h.App.DB, req.Code, req.AppID)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	resp := dto.MiniProgramLoginResponse{RequiresProfile: requiresProfile}
	if requiresProfile {
		resp.RegistrationToken = &regToken
	} else {
		resp.AccessToken = &access
		resp.User = miniUserRead(user)
	}
	respond.JSON(c, http.StatusOK, resp)
}

// Profile POST /mini-program/profile（registration token）
func (h *MiniHandler) Profile(c *gin.Context) {
	var req dto.MiniProgramProfileRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	appID, openid, ok := auth.MiniRegistrationOpenID(h.App.Cfg, c)
	if !ok {
		return
	}
	department := req.DepartmentName
	if department == "" {
		department = "华星检修维护部电气车间"
	}
	access, user, appErr := service.RegisterProfile(h.App.Cfg, h.App.DB, appID, openid, req.DisplayName, department)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	resp := dto.MiniProgramLoginResponse{}
	if access != "" {
		resp.AccessToken = &access
	}
	resp.User = miniUserRead(user)
	respond.JSON(c, http.StatusOK, resp)
}

// Me GET /mini-program/me
func (h *MiniHandler) Me(c *gin.Context) {
	user := auth.CurrentMiniUser(c)
	respond.JSON(c, http.StatusOK, miniUserRead(user))
}

// Inventory GET /mini-program/inventory
func (h *MiniHandler) Inventory(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.SearchMiniInventory(h.App.DB, c.Query("keyword"), c.Query("stock_status"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.MiniProgramInventoryItemRead, 0, len(items))
	for _, item := range items {
		var minQty *string
		if item.MinimumQty != nil {
			s := serialize.DecimalToString(*item.MinimumQty)
			minQty = &s
		}
		reads = append(reads, dto.MiniProgramInventoryItemRead{
			MaterialID: item.MaterialID, UUID: item.UUID, Name: item.Name, NameID: item.NameID,
			Alias: item.Alias, ModelSpec: item.ModelSpec, UnitName: item.UnitName,
			Quantity: serialize.DecimalToString(item.Quantity), MinimumQty: minQty,
			StockStatus: item.StockStatus, Remark: item.Remark,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.MiniProgramInventoryItemRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// LiteInventory GET /mini-program/lite-inventory
func (h *MiniHandler) LiteInventory(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.SearchLiteInventory(h.App.DB, c.Query("name"), c.Query("model_spec"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.MiniProgramLiteInventoryItemRead, 0, len(items))
	for i := range items {
		var qty *string
		if items[i].Quantity != nil {
			s := serialize.DecimalToString(items[i].Quantity.Decimal)
			qty = &s
		}
		reads = append(reads, dto.MiniProgramLiteInventoryItemRead{
			ID: items[i].ID, Name: items[i].Name, ModelSpec: items[i].ModelSpec,
			UnitName: items[i].UnitName, Quantity: qty, Remark: items[i].Remark,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.MiniProgramLiteInventoryItemRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// MaterialCodes GET /mini-program/material-codes
func (h *MiniHandler) MaterialCodes(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.SearchMaterialCodes(h.App.DB, c.Query("keyword"), "", "", "", page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.MiniProgramMaterialCodeRead, 0, len(items))
	for i := range items {
		reads = append(reads, dto.MiniProgramMaterialCodeRead{
			ID: items[i].ID, MaterialCode: items[i].MaterialCode, Name: items[i].Name,
			ModelSpec: items[i].ModelSpec, UnitName: items[i].UnitName,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.MiniProgramMaterialCodeRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// HuaXingInventory GET /mini-program/huaxing-inventory
func (h *MiniHandler) HuaXingInventory(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.SearchHuaXingInventory(h.App.DB, c.Query("keyword"), "", "", "", "", "", page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.MiniProgramHuaXingInventoryRead, 0, len(items))
	for i := range items {
		var qty *string
		if items[i].Quantity != nil {
			s := serialize.DecimalToString(items[i].Quantity.Decimal)
			qty = &s
		}
		reads = append(reads, dto.MiniProgramHuaXingInventoryRead{
			ID: items[i].ID, FirstInboundDate: datePtr(items[i].FirstInboundDate),
			Warehouse: items[i].Warehouse, MaterialCode: items[i].MaterialCode, Name: items[i].Name,
			ModelSpec: items[i].ModelSpec, Quantity: qty, UnitName: items[i].UnitName,
			Purchaser: items[i].Purchaser, PurchaseDepartment: items[i].PurchaseDepartment,
			SubitemNoName: items[i].SubitemNoName,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.MiniProgramHuaXingInventoryRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// PurchasePlans GET /mini-program/purchase-plans
func (h *MiniHandler) PurchasePlans(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.SearchMiniPurchasePlans(h.App.DB, c.Query("keyword"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.MiniProgramPurchasePlanItemRead, 0, len(items))
	for _, item := range items {
		reads = append(reads, dto.MiniProgramPurchasePlanItemRead{
			ID: item.ID, Name: item.Name, ModelSpec: item.ModelSpec, UnitName: item.UnitName,
			PlannedQty:         serialize.DecimalToString(item.PlannedQty),
			ActualDemandPerson: item.ActualDemandPerson, SubitemNo: item.SubitemNo, PlanNo: item.PlanNo,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.MiniProgramPurchasePlanItemRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// PurchaseRecords GET /mini-program/purchase-records
func (h *MiniHandler) PurchaseRecords(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.SearchMiniPurchaseRecords(h.App.DB, c.Query("keyword"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.MiniProgramPurchaseRecordItemRead, 0, len(items))
	for _, item := range items {
		reads = append(reads, dto.MiniProgramPurchaseRecordItemRead{
			ID: item.ID, MaterialName: item.MaterialName, ModelSpec: item.ModelSpec,
			UnitName: item.UnitName, PurchaseQty: serialize.DecimalToString(item.PurchaseQty),
			Status: item.Status, PlanNo: item.PlanNo,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.MiniProgramPurchaseRecordItemRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// OutboundReasons GET /mini-program/outbound-reasons
func (h *MiniHandler) OutboundReasons(c *gin.Context) {
	respond.JSON(c, http.StatusOK, dto.MiniProgramOutboundReasonOptions{Reasons: service.MiniOutboundReasons()})
}

// Outbound POST /mini-program/outbound
func (h *MiniHandler) Outbound(c *gin.Context) {
	var req dto.MiniProgramOutboundCreate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	occurredAt, err := serialize.ParseDateTime(req.OccurredAt)
	if err != nil {
		respond.Error(c, appErrNew("VALIDATION_ERROR", "occurred_at 必须是带时区的 ISO 时间", 422, nil))
		return
	}
	user := auth.CurrentMiniUser(c)
	item, appErr := service.MiniOutbound(h.App.DB, req.MaterialUUID, req.ClientRequestID,
		occurredAt, req.Quantity.Decimal, req.BusinessReason, trimmedPtr(req.ReceiverUnit),
		trimmedPtr(req.SubitemNo), user)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusCreated, operationRead(item))
}

// Operations GET /mini-program/operations
func (h *MiniHandler) Operations(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	user := auth.CurrentMiniUser(c)
	_ = user
	items, total, appErr := service.SearchOperations(h.App.DB, c.Query("operation_no"),
		"OUTBOUND", "", "MINI_PROGRAM", nil, nil, page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.MiniProgramOperationRead, 0, len(items))
	for i := range items {
		item := &items[i]
		var qty, before, after string
		var materialName, modelSpec, unitName string
		if len(item.Lines) > 0 {
			line := item.Lines[0]
			qty = serialize.DecimalToString(line.Quantity.Decimal)
			before = serialize.DecimalToString(line.BeforeQty.Decimal)
			after = serialize.DecimalToString(line.AfterQty.Decimal)
			materialName = line.MaterialNameSnapshot
			modelSpec = line.ModelSpecSnapshot
			unitName = line.UnitNameSnapshot
		}
		reads = append(reads, dto.MiniProgramOperationRead{
			ID: item.ID, OperationNo: item.OperationNo, OccurredAt: serialize.UTCZTime(item.OccurredAt),
			MaterialName: materialName, ModelSpec: modelSpec, UnitName: unitName,
			Quantity: qty, BeforeQty: before, AfterQty: after,
			ReceiverUnit: item.ReceiverUnit, ReceiverName: item.ReceiverName,
			SubitemNo: item.SubitemNo, BusinessReason: item.BusinessReason,
			MiniProgramUserName: item.MiniProgramUserNameSnapshot,
		})
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.MiniProgramOperationRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// OutboundByNo GET /mini-program/outbound/{operation_no}
func (h *MiniHandler) OutboundByNo(c *gin.Context) {
	item, appErr := service.MiniOperationByNo(h.App.DB, c.Param("operation_no"))
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	var out dto.MiniProgramOutboundRead
	out.OperationNo = item.OperationNo
	out.OccurredAt = serialize.UTCZTime(item.OccurredAt)
	if len(item.Lines) > 0 {
		line := item.Lines[0]
		out.MaterialName = line.MaterialNameSnapshot
		out.ModelSpec = line.ModelSpecSnapshot
		out.UnitName = line.UnitNameSnapshot
		out.Quantity = serialize.DecimalToString(line.Quantity.Decimal)
	}
	respond.JSON(c, http.StatusOK, out)
}

// MiniUsers GET /mini-program-users
func (h *MiniHandler) MiniUsers(c *gin.Context) {
	page, appErr := binding.QueryInt(c, "page", 1, 1, 1<<31-1)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	pageSize, appErr := binding.QueryInt(c, "page_size", 20, 1, 200)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	items, total, appErr := service.MiniProgramUsers(h.App.DB, c.Query("keyword"), page, pageSize)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	reads := make([]dto.MiniProgramUserRead, 0, len(items))
	for i := range items {
		reads = append(reads, *miniUserRead(&items[i]))
	}
	respond.JSON(c, http.StatusOK, dto.Page[dto.MiniProgramUserRead]{
		Items: reads, Page: page, PageSize: pageSize, Total: total,
	})
}

// MiniUserUpdate PATCH /mini-program-users/{user_id}
func (h *MiniHandler) MiniUserUpdate(c *gin.Context) {
	userID, ok := parseIDParam(c, "user_id")
	if !ok {
		return
	}
	var req dto.MiniProgramUserUpdate
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	var user models.MiniProgramUser
	if err := h.App.DB.First(&user, userID).Error; err != nil {
		respond.Error(c, appErrNew("NOT_FOUND", "小程序用户不存在", 400, nil))
		return
	}
	if appErr := service.ValidateVersion(req.Version, user.Version); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	updates := map[string]any{}
	if req.DisplayName != nil {
		updates["display_name"] = *req.DisplayName
	}
	if req.DepartmentName != nil {
		updates["department_name"] = *req.DepartmentName
	}
	if req.Enabled != nil {
		updates["enabled"] = *req.Enabled
	}
	updates["version"] = gorm.Expr("version + 1")
	if err := h.App.DB.Model(&models.MiniProgramUser{}).Where("id = ?", userID).Updates(updates).Error; err != nil {
		respond.Error(c, service.DatabaseError(err))
		return
	}
	var updated models.MiniProgramUser
	h.App.DB.First(&updated, userID)
	db2 := h.App.DB
	db2.Where("mini_program_user_id = ?", userID).Order("app_id").Find(&updated.Identities)
	respond.JSON(c, http.StatusOK, miniUserRead(&updated))
}

// MiniUserDelete DELETE /mini-program-users/{user_id}
func (h *MiniHandler) MiniUserDelete(c *gin.Context) {
	userID, ok := parseIDParam(c, "user_id")
	if !ok {
		return
	}
	if err := h.App.DB.Transaction(func(tx *gormDB) error {
		if err := tx.Delete(&models.MiniProgramIdentity{}, "mini_program_user_id = ?", userID).Error; err != nil {
			return err
		}
		return tx.Delete(&models.MiniProgramUser{}, userID).Error
	}); err != nil {
		respond.Error(c, service.DatabaseError(err))
		return
	}
	c.Status(http.StatusNoContent)
}

// MiniUserMerge POST /mini-program-users/{target_user_id}/merge
func (h *MiniHandler) MiniUserMerge(c *gin.Context) {
	targetID, ok := parseIDParam(c, "target_user_id")
	if !ok {
		return
	}
	var req dto.MiniProgramMergeRequest
	if appErr := binding.Body(c, &req); appErr != nil {
		respond.Error(c, appErr)
		return
	}
	updated, appErr := service.MergeMiniUsers(h.App.DB, targetID, req.SourceUserID, req.TargetVersion, req.SourceVersion)
	if appErr != nil {
		respond.Error(c, appErr)
		return
	}
	respond.JSON(c, http.StatusOK, miniUserRead(updated))
}

// RegisterMini 注册小程序路由。
func RegisterMini(r *gin.RouterGroup, app *App) {
	h := NewMiniHandler(app)
	mini := r.Group("/mini-program")
	mini.POST("/auth/wx-login", h.WXLogin)
	mini.POST("/profile", h.Profile)
	authMini := mini.Group("", auth.AuthMiniProgram(app.Cfg, app.DB))
	authMini.GET("/me", h.Me)
	authMini.GET("/inventory", h.Inventory)
	authMini.GET("/lite-inventory", h.LiteInventory)
	authMini.GET("/material-codes", h.MaterialCodes)
	authMini.GET("/huaxing-inventory", h.HuaXingInventory)
	authMini.GET("/purchase-plans", h.PurchasePlans)
	authMini.GET("/purchase-records", h.PurchaseRecords)
	authMini.GET("/outbound-reasons", h.OutboundReasons)
	authMini.POST("/outbound", h.Outbound)
	authMini.GET("/operations", h.Operations)
	authMini.GET("/outbound/:operation_no", h.OutboundByNo)
	authMini.GET("/inventory/last-import", setType("LITE_INVENTORY"), h.LastImport)
	authMini.GET("/material-codes/last-import", setType("MATERIAL_CODE_LIBRARY"), h.LastImport)
	authMini.GET("/huaxing-inventory/last-import", setType("HUAXING_INVENTORY"), h.LastImport)

	users := r.Group("/mini-program-users", auth.AuthManagement(app.Cfg, app.DB), auth.SuperAdmin())
	users.GET("", h.MiniUsers)
	users.PATCH("/:user_id", h.MiniUserUpdate)
	users.DELETE("/:user_id", h.MiniUserDelete)
	users.POST("/:target_user_id/merge", h.MiniUserMerge)
}

// LastImport GET /mini-program/{type}/last-import
func (h *MiniHandler) LastImport(c *gin.Context) {
	importType := c.Param("import_type")
	lastAt := service.LatestImportFinishedAt(h.App.DB, importType)
	var last *serialize.OffsetTime
	if lastAt != nil {
		t := serialize.OffsetTime(*lastAt)
		last = &t
	}
	respond.JSON(c, http.StatusOK, dto.LastImportRead{LastImportAt: last})
}
