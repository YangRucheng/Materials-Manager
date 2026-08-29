// Package dto 定义请求/响应数据结构（与 docs/openapi.yaml 契约一致）。
// 字段名 snake_case；可空字段输出 null（不加 omitempty）。
package dto

import (
	"encoding/json"
	"strings"

	"github.com/shopspring/decimal"

	"github.com/yangrucheng/materials-manager/server/internal/models"
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
)

// ============ 认证 ============

type LoginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required,min=1,max=128"`
}

type LoginResponse struct {
	AccessToken  string   `json:"access_token"`
	RefreshToken string   `json:"refresh_token"`
	TokenType    string   `json:"token_type"`
	User         UserRead `json:"user"`
}

type RefreshTokenRequest struct {
	RefreshToken string `json:"refresh_token" binding:"required,min=1,max=4096"`
}

type TokenPairResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	TokenType    string `json:"token_type"`
}

// ============ 用户 ============

type UserRead struct {
	ID          int64  `json:"id"`
	Username    string `json:"username"`
	DisplayName string `json:"display_name"`
	Role        string `json:"role"`
	Enabled     bool   `json:"enabled"`
	Version     int    `json:"version"`
}

func NewUserRead(u *models.User) UserRead {
	return UserRead{
		ID:          u.ID,
		Username:    u.Username,
		DisplayName: u.DisplayName,
		Role:        u.Role,
		Enabled:     u.Enabled,
		Version:     u.Version,
	}
}

type UserApiTokenRead struct {
	UserRead
	// api_token 仅在新建/重新生成接口返回一次明文；列表读取为 null。
	APIToken *string `json:"api_token"`
}

func NewUserApiTokenRead(u *models.User) UserApiTokenRead {
	out := UserApiTokenRead{UserRead: NewUserRead(u)}
	if u.APIToken != "" {
		token := u.APIToken
		out.APIToken = &token
	}
	return out
}

type UserCreate struct {
	Username    string `json:"username" binding:"required,min=3,max=64"`
	Password    string `json:"password" binding:"required,min=6,max=128"`
	DisplayName string `json:"display_name" binding:"required,min=1,max=128"`
	Role        string `json:"role" binding:"required,oneof=SUPER_ADMIN WAREHOUSE_ADMIN PURCHASE_ADMIN READ_ONLY"`
	Enabled     *bool  `json:"enabled"`
}

type UserUpdate struct {
	Username    *string `json:"username" binding:"omitempty,min=3,max=64"`
	DisplayName *string `json:"display_name" binding:"omitempty,min=1,max=128"`
	Password    *string `json:"password" binding:"omitempty,min=6,max=128"`
	Role        *string `json:"role" binding:"omitempty,oneof=SUPER_ADMIN WAREHOUSE_ADMIN PURCHASE_ADMIN READ_ONLY"`
	Enabled     *bool   `json:"enabled"`
	Version     int     `json:"version" binding:"required"`
}

type UserApiTokenRegenerate struct {
	Version int `json:"version" binding:"required"`
}

// ============ 分页 ============

type Page[T any] struct {
	Items    []T `json:"items"`
	Page     int `json:"page"`
	PageSize int `json:"page_size"`
	Total    int `json:"total"`
}

// ============ 图片 ============

type FileObjectRead struct {
	ID           string `json:"id"`
	OriginalName string `json:"original_name"`
	MimeType     string `json:"mime_type"`
	SizeBytes    int64  `json:"size_bytes"`
	Width        int    `json:"width"`
	Height       int    `json:"height"`
}

func NewFileObjectRead(f *models.FileObject) FileObjectRead {
	return FileObjectRead{
		ID:           f.ID,
		OriginalName: f.OriginalName,
		MimeType:     f.MimeType,
		SizeBytes:    f.SizeBytes,
		Width:        f.Width,
		Height:       f.Height,
	}
}

// ============ 二级库物资 ============

type ReplenishmentPolicyRead struct {
	MinimumQty string `json:"minimum_qty"`
	Enabled    bool   `json:"enabled"`
	Version    int    `json:"version"`
}

type StockMaterialRead struct {
	ID                  int64                    `json:"id"`
	UUID                string                   `json:"uuid"`
	Name                string                   `json:"name"`
	NameID              *string                  `json:"name_id"`
	Alias               *string                  `json:"alias"`
	ModelSpec           string                   `json:"model_spec"`
	UnitName            string                   `json:"unit_name"`
	Remark              *string                  `json:"remark"`
	CurrentQty          string                   `json:"current_qty"`
	Images              []FileObjectRead         `json:"images"`
	ReplenishmentPolicy *ReplenishmentPolicyRead `json:"replenishment_policy"`
	HasOperationRecords bool                     `json:"has_operation_records"`
	CreatedAt           serialize.UTCZTime       `json:"created_at"`
	UpdatedAt           serialize.UTCZTime       `json:"updated_at"`
	Version             int                      `json:"version"`
}

type StockMaterialCreate struct {
	Name      string   `json:"name" binding:"required,max=128"`
	NameID    *string  `json:"name_id" binding:"omitempty,max=128"`
	Alias     *string  `json:"alias" binding:"omitempty,max=128"`
	ModelSpec string   `json:"model_spec" binding:"required,max=255"`
	UnitName  string   `json:"unit_name" binding:"required,max=32"`
	Remark    *string  `json:"remark" binding:"omitempty,max=1000"`
	ImageIDs  []string `json:"image_ids" binding:"required"`
}

type StockMaterialUpdate struct {
	Name      string   `json:"name" binding:"required,max=128"`
	NameID    *string  `json:"name_id" binding:"omitempty,max=128"`
	Alias     *string  `json:"alias" binding:"omitempty,max=128"`
	ModelSpec string   `json:"model_spec" binding:"required,max=255"`
	UnitName  string   `json:"unit_name" binding:"required,max=32"`
	Remark    *string  `json:"remark" binding:"omitempty,max=1000"`
	ImageIDs  []string `json:"image_ids" binding:"required"`
	Version   int      `json:"version" binding:"required"`
}

type ReplenishmentPolicyWrite struct {
	MinimumQty string `json:"minimum_qty" binding:"required"`
	Enabled    bool   `json:"enabled"`
	Version    int    `json:"version"`
}

// ============ 库存余额 ============

type InventoryBalanceRead struct {
	StockMaterialID      int64              `json:"stock_material_id"`
	Name                 string             `json:"name"`
	Alias                *string            `json:"alias"`
	ModelSpec            string             `json:"model_spec"`
	UnitName             string             `json:"unit_name"`
	CurrentQty           string             `json:"current_qty"`
	MinimumQty           *string            `json:"minimum_qty"`
	IsLowStock           bool               `json:"is_low_stock"`
	SuggestedPurchaseQty string             `json:"suggested_purchase_qty"`
	UpdatedAt            serialize.UTCZTime `json:"updated_at"`
}

// ============ 库存流水 ============

// Quantity 请求数量：兼容 JSON 数字与字符串。
type Quantity struct {
	Decimal decimal.Decimal
}

func (q *Quantity) UnmarshalJSON(data []byte) error {
	trimmed := strings.TrimSpace(string(data))
	if trimmed == "" || trimmed == "null" {
		return nil
	}
	if trimmed[0] == '"' {
		var s string
		if err := json.Unmarshal(data, &s); err != nil {
			return err
		}
		d, err := decimal.NewFromString(strings.TrimSpace(s))
		if err != nil {
			return err
		}
		q.Decimal = d
		return nil
	}
	var n float64
	if err := json.Unmarshal(data, &n); err != nil {
		return err
	}
	q.Decimal = decimal.NewFromFloat(n)
	return nil
}

type OperationLineWrite struct {
	StockMaterialID int64    `json:"stock_material_id" binding:"required"`
	Quantity        Quantity `json:"quantity" binding:"required"`
}

type OperationCreate struct {
	ClientRequestID string               `json:"client_request_id" binding:"required,max=64"`
	OccurredAt      string               `json:"occurred_at" binding:"required"`
	SourceType      string               `json:"source_type" binding:"required,oneof=MANUAL MINI_PROGRAM REVERSAL INITIALIZATION"`
	BusinessReason  string               `json:"business_reason" binding:"max=500"`
	ReceiverUnit    *string              `json:"receiver_unit" binding:"omitempty,max=128"`
	ReceiverName    *string              `json:"receiver_name" binding:"omitempty,max=64"`
	SubitemNo       *string              `json:"subitem_no" binding:"omitempty,max=64"`
	Lines           []OperationLineWrite `json:"lines" binding:"required,min=1"`
}

type OperationUpdate struct {
	OperationType  string               `json:"operation_type" binding:"required,oneof=INBOUND OUTBOUND"`
	OccurredAt     string               `json:"occurred_at" binding:"required"`
	SourceType     string               `json:"source_type" binding:"required,oneof=MANUAL MINI_PROGRAM REVERSAL INITIALIZATION"`
	BusinessReason string               `json:"business_reason" binding:"max=500"`
	ReceiverUnit   *string              `json:"receiver_unit" binding:"omitempty,max=128"`
	ReceiverName   *string              `json:"receiver_name" binding:"omitempty,max=64"`
	SubitemNo      *string              `json:"subitem_no" binding:"omitempty,max=64"`
	Lines          []OperationLineWrite `json:"lines" binding:"required,min=1"`
	Version        int                  `json:"version" binding:"required"`
}

type ReverseOperationRequest struct {
	ClientRequestID string               `json:"client_request_id" binding:"required,max=64"`
	Reason          string               `json:"reason" binding:"required,max=500"`
	Lines           []OperationLineWrite `json:"lines" binding:"required,min=1"`
}

type StockOperationLineRead struct {
	ID              int64  `json:"id"`
	StockMaterialID int64  `json:"stock_material_id"`
	MaterialName    string `json:"material_name"`
	ModelSpec       string `json:"model_spec"`
	UnitName        string `json:"unit_name"`
	Quantity        string `json:"quantity"`
	RemainingQty    string `json:"remaining_qty"`
	BeforeQty       string `json:"before_qty"`
	AfterQty        string `json:"after_qty"`
}

type StockOperationRead struct {
	ID                  int64                    `json:"id"`
	OperationNo         string                   `json:"operation_no"`
	OperationType       string                   `json:"operation_type"`
	OccurredAt          serialize.UTCZTime       `json:"occurred_at"`
	BusinessReason      string                   `json:"business_reason"`
	ReceiverUnit        *string                  `json:"receiver_unit"`
	ReceiverName        *string                  `json:"receiver_name"`
	SubitemNo           *string                  `json:"subitem_no"`
	SourceType          string                   `json:"source_type"`
	ReversalOfID        *int64                   `json:"reversal_of_id"`
	IsReversed          bool                     `json:"is_reversed"`
	ClientRequestID     string                   `json:"client_request_id"`
	MiniProgramUserName *string                  `json:"mini_program_user_name"`
	Lines               []StockOperationLineRead `json:"lines"`
	CreatedAt           serialize.UTCZTime       `json:"created_at"`
	Version             int                      `json:"version"`
}

// ============ 补库 ============

type ReplenishmentDefaultsRead struct {
	PurchaseResponsible string         `json:"purchase_responsible"`
	DemandDate          serialize.Date `json:"demand_date"`
}

type ReplenishmentDraftCreate struct {
	DemandDate          string   `json:"demand_date" binding:"required"`
	ActualDemandPerson  string   `json:"actual_demand_person" binding:"required,max=128"`
	PurchaseResponsible string   `json:"purchase_responsible" binding:"required,max=128"`
	PlannedQty          Quantity `json:"planned_qty" binding:"required"`
}

type ReplenishmentDraftRead struct {
	Next       string `json:"next"`
	ResourceID int64  `json:"resource_id"`
}

// ============ 仪表盘 ============

type DashboardSummaryRead struct {
	StockMaterialCount           int `json:"stock_material_count"`
	LowStockCount                int `json:"low_stock_count"`
	UncodedPurchaseMaterialCount int `json:"uncoded_purchase_material_count"`
	PurchaseRecordCount          int `json:"purchase_record_count"`
}
