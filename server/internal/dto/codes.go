package dto

import (
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
)

// ============ 编码库 / 外部库存 / 精简二级库 ============

type MaterialCodeLibraryRead struct {
	ID           int64   `json:"id"`
	MaterialCode string  `json:"material_code"`
	Name         *string `json:"name"`
	ModelSpec    *string `json:"model_spec"`
	UnitName     string  `json:"unit_name"`
}

type MaterialCodeExistsRead struct {
	MaterialCode string `json:"material_code"`
	Exists       bool   `json:"exists"`
}

type HuaXingInventoryRead struct {
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

type HuaXingFilterOptions struct {
	PurchaseDepartments []string `json:"purchase_departments"`
	Purchasers          []string `json:"purchasers"`
}

type LiteInventoryRead struct {
	ID        int64   `json:"id"`
	Name      string  `json:"name"`
	ModelSpec *string `json:"model_spec"`
	UnitName  *string `json:"unit_name"`
	Quantity  *string `json:"quantity"`
	Remark    *string `json:"remark"`
}

type LastImportRead struct {
	LastImportAt *serialize.OffsetTime `json:"last_import_at"`
}

type ExcelImportJobRead struct {
	ID               int64                 `json:"id"`
	ImportType       string                `json:"import_type"`
	Status           string                `json:"status"`
	OriginalFilename string                `json:"original_filename"`
	Result           map[string]any        `json:"result"`
	ErrorCode        *string               `json:"error_code"`
	ErrorMessage     *string               `json:"error_message"`
	CreatedAt        serialize.OffsetTime  `json:"created_at"`
	StartedAt        *serialize.OffsetTime `json:"started_at"`
	FinishedAt       *serialize.OffsetTime `json:"finished_at"`
}
