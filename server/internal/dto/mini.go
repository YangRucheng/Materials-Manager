package dto

import (
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
)

type MiniProgramLoginResponse struct {
	AccessToken       *string              `json:"access_token"`
	RefreshToken      *string              `json:"refresh_token"`
	User              *MiniProgramUserRead `json:"user"`
	RequiresProfile   bool                 `json:"requires_profile"`
	RegistrationToken *string              `json:"registration_token"`
}

type MiniProgramProfileRequest struct {
	DisplayName    string `json:"display_name" binding:"required,max=128"`
	DepartmentName string `json:"department_name" binding:"omitempty,max=128"`
}

type MiniProgramUserRead struct {
	ID             int64                     `json:"id"`
	DisplayName    string                    `json:"display_name"`
	DepartmentName string                    `json:"department_name"`
	Enabled        bool                      `json:"enabled"`
	Identities     []MiniProgramIdentityRead `json:"identities"`
	CreatedAt      serialize.UTCZTime        `json:"created_at"`
	UpdatedAt      serialize.UTCZTime        `json:"updated_at"`
	Version        int                       `json:"version"`
}

type MiniProgramIdentityRead struct {
	ID           int64              `json:"id"`
	AppID        string             `json:"app_id"`
	WechatOpenid string             `json:"wechat_openid"`
	CreatedAt    serialize.UTCZTime `json:"created_at"`
}

type MiniProgramUserUpdate struct {
	DisplayName    *string `json:"display_name" binding:"omitempty,max=128"`
	DepartmentName *string `json:"department_name" binding:"omitempty,max=128"`
	Enabled        *bool   `json:"enabled"`
	Version        int     `json:"version" binding:"required"`
}

type MiniProgramMergeRequest struct {
	SourceUserID  int64 `json:"source_user_id" binding:"required"`
	TargetVersion int   `json:"target_version" binding:"required"`
	SourceVersion int   `json:"source_version" binding:"required"`
}

type MiniProgramInventoryItemRead struct {
	MaterialID  int64   `json:"material_id"`
	UUID        string  `json:"uuid"`
	Name        string  `json:"name"`
	NameID      *string `json:"name_id"`
	Alias       *string `json:"alias"`
	ModelSpec   string  `json:"model_spec"`
	UnitName    string  `json:"unit_name"`
	Quantity    string  `json:"quantity"`
	MinimumQty  *string `json:"minimum_qty"`
	StockStatus string  `json:"stock_status"`
	Remark      *string `json:"remark"`
}

type MiniProgramLiteInventoryItemRead struct {
	ID        int64   `json:"id"`
	Name      string  `json:"name"`
	ModelSpec *string `json:"model_spec"`
	UnitName  *string `json:"unit_name"`
	Quantity  *string `json:"quantity"`
	Remark    *string `json:"remark"`
}

type MiniProgramMaterialCodeRead struct {
	ID           int64   `json:"id"`
	MaterialCode string  `json:"material_code"`
	Name         *string `json:"name"`
	ModelSpec    *string `json:"model_spec"`
	UnitName     string  `json:"unit_name"`
}

type MiniProgramHuaXingInventoryRead struct {
	ID                 int64           `json:"id"`
	FirstInboundDate   *serialize.Date `json:"first_inbound_date"`
	Warehouse          *string         `json:"warehouse"`
	MaterialCode       *string         `json:"material_code"`
	Name               *string         `json:"name"`
	ModelSpec          *string         `json:"model_spec"`
	Quantity           *string         `json:"quantity"`
	UnitName           *string         `json:"unit_name"`
	Purchaser          *string         `json:"purchaser"`
	PurchaseDepartment *string         `json:"purchase_department"`
	SubitemNoName      *string         `json:"subitem_no_name"`
}

type MiniProgramPurchasePlanItemRead struct {
	ID                 int64   `json:"id"`
	Name               string  `json:"name"`
	ModelSpec          string  `json:"model_spec"`
	UnitName           string  `json:"unit_name"`
	PlannedQty         string  `json:"planned_qty"`
	ActualDemandPerson string  `json:"actual_demand_person"`
	SubitemNo          *string `json:"subitem_no"`
	PlanNo             string  `json:"plan_no"`
}

type MiniProgramPurchaseRecordItemRead struct {
	ID           int64  `json:"id"`
	MaterialName string `json:"material_name"`
	ModelSpec    string `json:"model_spec"`
	UnitName     string `json:"unit_name"`
	PurchaseQty  string `json:"purchase_qty"`
	Status       string `json:"status"`
	PlanNo       string `json:"plan_no"`
}

type MiniProgramOutboundCreate struct {
	ClientRequestID string   `json:"client_request_id" binding:"required,max=64"`
	MaterialUUID    string   `json:"material_uuid" binding:"required"`
	OccurredAt      string   `json:"occurred_at" binding:"required"`
	Quantity        Quantity `json:"quantity" binding:"required"`
	BusinessReason  string   `json:"business_reason" binding:"required,max=500"`
	ReceiverUnit    *string  `json:"receiver_unit" binding:"omitempty,max=128"`
	SubitemNo       *string  `json:"subitem_no" binding:"omitempty,max=64"`
}

type MiniProgramOperationRead struct {
	ID                  int64              `json:"id"`
	OperationNo         string             `json:"operation_no"`
	OccurredAt          serialize.UTCZTime `json:"occurred_at"`
	MaterialName        string             `json:"material_name"`
	ModelSpec           string             `json:"model_spec"`
	UnitName            string             `json:"unit_name"`
	Quantity            string             `json:"quantity"`
	BeforeQty           string             `json:"before_qty"`
	AfterQty            string             `json:"after_qty"`
	ReceiverUnit        *string            `json:"receiver_unit"`
	ReceiverName        *string            `json:"receiver_name"`
	SubitemNo           *string            `json:"subitem_no"`
	BusinessReason      string             `json:"business_reason"`
	MiniProgramUserName *string            `json:"mini_program_user_name"`
}

type MiniProgramOutboundRead struct {
	OperationNo  string             `json:"operation_no"`
	MaterialName string             `json:"material_name"`
	ModelSpec    string             `json:"model_spec"`
	UnitName     string             `json:"unit_name"`
	Quantity     string             `json:"quantity"`
	OccurredAt   serialize.UTCZTime `json:"occurred_at"`
}

type MiniProgramOutboundReasonOptions struct {
	Reasons []string `json:"reasons"`
}
