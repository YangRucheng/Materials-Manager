package dto

import (
	"github.com/yangrucheng/materials-manager/server/internal/serialize"
)

// ============ 申购计划 ============

type PurchaseMaterialRead struct {
	ID                  int64              `json:"id"`
	PlanNo              string             `json:"plan_no"`
	PlanDate            serialize.Date     `json:"plan_date"`
	MaterialCode        *string            `json:"material_code"`
	Category            *string            `json:"category"`
	Urgency             string             `json:"urgency"`
	DemandDepartment    string             `json:"demand_department"`
	Name                string             `json:"name"`
	ModelSpec           string             `json:"model_spec"`
	UnitName            string             `json:"unit_name"`
	ActualDemandPerson  string             `json:"actual_demand_person"`
	PurchaseResponsible string             `json:"purchase_responsible"`
	PlannedQty          string             `json:"planned_qty"`
	Usage               string             `json:"usage"`
	SubitemNo           *string            `json:"subitem_no"`
	Remark              *string            `json:"remark"`
	StockMaterialID     *int64             `json:"stock_material_id"`
	StockMaterialName   *string            `json:"stock_material_name"`
	Status              string             `json:"status"`
	MovedToRecord       bool               `json:"moved_to_record"`
	Images              []FileObjectRead   `json:"images"`
	CreatedAt           serialize.UTCZTime `json:"created_at"`
	UpdatedAt           serialize.UTCZTime `json:"updated_at"`
	Version             int                `json:"version"`
}

// PurchaseMaterialBase 计划创建/更新公共字段。
type PurchaseMaterialBase struct {
	PlanDate            *string  `json:"plan_date"`
	MaterialCode        *string  `json:"material_code" binding:"omitempty,max=64"`
	Category            *string  `json:"category" binding:"omitempty,max=64"`
	Urgency             string   `json:"urgency" binding:"omitempty,max=32"`
	DemandDepartment    string   `json:"demand_department" binding:"omitempty,max=128"`
	Name                string   `json:"name" binding:"required,max=128"`
	ModelSpec           string   `json:"model_spec" binding:"required,max=255"`
	UnitName            string   `json:"unit_name" binding:"required,max=32"`
	ActualDemandPerson  *string  `json:"actual_demand_person" binding:"omitempty,max=128"`
	PurchaseResponsible *string  `json:"purchase_responsible" binding:"omitempty,max=128"`
	PlannedQty          Quantity `json:"planned_qty" binding:"required"`
	Usage               string   `json:"usage" binding:"required,max=500"`
	SubitemNo           *string  `json:"subitem_no" binding:"omitempty,max=64"`
	Remark              *string  `json:"remark" binding:"omitempty,max=1000"`
	StockMaterialID     *int64   `json:"stock_material_id"`
	ImageIDs            []string `json:"image_ids"`
	Status              *string  `json:"status"`
}

type PurchaseMaterialCreate struct {
	PurchaseMaterialBase
}

type PurchaseMaterialUpdate struct {
	PurchaseMaterialBase
	Version int `json:"version" binding:"required"`
}

// BatchUpdate 批量更新：逐行引用 + 共享的可选字段。
type BatchUpdatePurchasePlansRequest struct {
	Materials           []BatchUpdateReference `json:"materials" binding:"required,min=1"`
	PlanDate            *string                `json:"plan_date"`
	Category            *string                `json:"category"`
	Urgency             *string                `json:"urgency"`
	DemandDepartment    *string                `json:"demand_department"`
	ActualDemandPerson  *string                `json:"actual_demand_person"`
	PurchaseResponsible *string                `json:"purchase_responsible"`
	SubitemNo           *string                `json:"subitem_no"`
	Usage               *string                `json:"usage"`
	Status              *string                `json:"status"`
}

type BatchUpdateReference struct {
	ID      int64 `json:"id" binding:"required"`
	Version int   `json:"version" binding:"required"`
}

type BatchMovePurchasePlansRequest struct {
	Materials []BatchUpdateReference `json:"materials" binding:"required,min=1"`
}

type MovePurchasePlanRequest struct {
	Version int `json:"version" binding:"required"`
}

type LinkStockMaterialRequest struct {
	StockMaterialID int64 `json:"stock_material_id" binding:"required"`
	Version         int   `json:"version" binding:"required"`
}

type PurchaseFilterOptions struct {
	ActualDemandPersons  []string `json:"actual_demand_persons"`
	PurchaseResponsibles []string `json:"purchase_responsibles"`
	SubitemNos           []string `json:"subitem_nos"`
	Categories           []string `json:"categories"`
}

// ============ 申购记录 ============

type PurchaseRecordRead struct {
	LineID              int64              `json:"line_id"`
	PurchaseRequestID   int64              `json:"purchase_request_id"`
	PurchaseMaterialID  *int64             `json:"purchase_material_id"`
	PlanNo              string             `json:"plan_no"`
	PlanDate            serialize.Date     `json:"plan_date"`
	PurchaseOrderNo     *string            `json:"purchase_order_no"`
	TraceNo             *string            `json:"trace_no"`
	ContractNo          *string            `json:"contract_no"`
	VesselNo            *string            `json:"vessel_no"`
	ConsolidationDate   *serialize.Date    `json:"consolidation_date"`
	ConsolidationPort   *string            `json:"consolidation_port"`
	SailingDate         *serialize.Date    `json:"sailing_date"`
	Status              string             `json:"status"`
	MaterialCode        *string            `json:"material_code"`
	Category            *string            `json:"category"`
	DemandDepartment    string             `json:"demand_department"`
	MaterialName        string             `json:"material_name"`
	ModelSpec           string             `json:"model_spec"`
	UnitName            string             `json:"unit_name"`
	PurchaseQty         string             `json:"purchase_qty"`
	ActualDemandPerson  string             `json:"actual_demand_person"`
	PurchaseResponsible string             `json:"purchase_responsible"`
	Salesperson         *string            `json:"salesperson"`
	PlanRemark          *string            `json:"plan_remark"`
	RecordRemark        *string            `json:"record_remark"`
	Usage               string             `json:"usage"`
	SubitemNo           *string            `json:"subitem_no"`
	Images              []FileObjectRead   `json:"images"`
	StockMaterialID     *int64             `json:"stock_material_id"`
	PurchaseDate        *serialize.Date    `json:"purchase_date"`
	CreatedAt           serialize.UTCZTime `json:"created_at"`
	UpdatedAt           serialize.UTCZTime `json:"updated_at"`
	Version             int                `json:"version"`
}

type PurchaseRecordUpdate struct {
	PlanDate            string   `json:"plan_date" binding:"required"`
	MaterialCode        *string  `json:"material_code" binding:"omitempty,max=64"`
	Category            *string  `json:"category" binding:"omitempty,max=64"`
	DemandDepartment    string   `json:"demand_department" binding:"omitempty,max=128"`
	MaterialName        string   `json:"material_name" binding:"required,max=128"`
	ModelSpec           string   `json:"model_spec" binding:"required,max=255"`
	UnitName            string   `json:"unit_name" binding:"required,max=32"`
	ActualDemandPerson  string   `json:"actual_demand_person" binding:"required,max=128"`
	PurchaseResponsible string   `json:"purchase_responsible" binding:"required,max=128"`
	PurchaseQty         Quantity `json:"purchase_qty" binding:"required"`
	Usage               string   `json:"usage" binding:"required,max=500"`
	SubitemNo           *string  `json:"subitem_no" binding:"omitempty,max=64"`
	Salesperson         *string  `json:"salesperson" binding:"omitempty,max=128"`
	Status              string   `json:"status" binding:"omitempty,max=128"`
	Version             int      `json:"version" binding:"required"`
	ImageIDs            []string `json:"image_ids"`
}

type BatchUpdatePurchaseRecordsRequest struct {
	Lines             []BatchUpdateReference `json:"lines" binding:"required,min=1"`
	PurchaseOrderNo   *string                `json:"purchase_order_no" binding:"omitempty,max=128"`
	ContractNo        *string                `json:"contract_no" binding:"omitempty,max=128"`
	VesselNo          *string                `json:"vessel_no" binding:"omitempty,max=128"`
	Salesperson       *string                `json:"salesperson" binding:"omitempty,max=128"`
	Status            *string                `json:"status" binding:"omitempty,max=128"`
	ConsolidationPort *string                `json:"consolidation_port" binding:"omitempty,max=128"`
	ConsolidationDate *string                `json:"consolidation_date"`
	SailingDate       *string                `json:"sailing_date"`
	PurchaseDate      *string                `json:"purchase_date"`
}

type PurchaseRecordFilterOptions struct {
	ActualDemandPersons  []string `json:"actual_demand_persons"`
	PurchaseResponsibles []string `json:"purchase_responsibles"`
	SubitemNos           []string `json:"subitem_nos"`
	Categories           []string `json:"categories"`
	Salespersons         []string `json:"salespersons"`
	Statuses             []string `json:"statuses"`
}

// ============ 周期性计划模板 ============

type PurchasePlanTemplateRead struct {
	ID                  int64              `json:"id"`
	MaterialCode        *string            `json:"material_code"`
	Category            *string            `json:"category"`
	Urgency             string             `json:"urgency"`
	DemandDepartment    string             `json:"demand_department"`
	Name                string             `json:"name"`
	ModelSpec           string             `json:"model_spec"`
	UnitName            string             `json:"unit_name"`
	ActualDemandPerson  string             `json:"actual_demand_person"`
	PurchaseResponsible string             `json:"purchase_responsible"`
	PlannedQty          string             `json:"planned_qty"`
	Usage               string             `json:"usage"`
	SubitemNo           *string            `json:"subitem_no"`
	Remark              *string            `json:"remark"`
	StockMaterialID     *int64             `json:"stock_material_id"`
	StockMaterialName   *string            `json:"stock_material_name"`
	Images              []FileObjectRead   `json:"images"`
	CreatedAt           serialize.UTCZTime `json:"created_at"`
	UpdatedAt           serialize.UTCZTime `json:"updated_at"`
	Version             int                `json:"version"`
}

type PurchasePlanTemplateCreate struct {
	MaterialCode        *string  `json:"material_code" binding:"omitempty,max=64"`
	Category            *string  `json:"category" binding:"omitempty,max=64"`
	Urgency             string   `json:"urgency" binding:"omitempty,max=32"`
	DemandDepartment    string   `json:"demand_department" binding:"omitempty,max=128"`
	Name                string   `json:"name" binding:"required,max=128"`
	ModelSpec           string   `json:"model_spec" binding:"required,max=255"`
	UnitName            string   `json:"unit_name" binding:"required,max=32"`
	ActualDemandPerson  *string  `json:"actual_demand_person" binding:"omitempty,max=128"`
	PurchaseResponsible *string  `json:"purchase_responsible" binding:"omitempty,max=128"`
	PlannedQty          Quantity `json:"planned_qty" binding:"required"`
	Usage               string   `json:"usage" binding:"required,max=500"`
	SubitemNo           *string  `json:"subitem_no" binding:"omitempty,max=64"`
	Remark              *string  `json:"remark" binding:"omitempty,max=1000"`
	StockMaterialID     *int64   `json:"stock_material_id"`
	ImageIDs            []string `json:"image_ids"`
}

type PurchasePlanTemplateUpdate struct {
	PurchasePlanTemplateCreate
	Version int `json:"version" binding:"required"`
}

type PurchasePlanTemplateFilterOptions struct {
	ActualDemandPersons  []string `json:"actual_demand_persons"`
	PurchaseResponsibles []string `json:"purchase_responsibles"`
	Categories           []string `json:"categories"`
}

// ============ 分享链接 ============

type ShareCreateRequest struct {
	ShareType string   `json:"share_type" binding:"required,oneof=purchase_plan purchase_record"`
	ItemIDs   []int64  `json:"item_ids" binding:"required,min=1"`
	ExpiresIn string   `json:"expires_in" binding:"required,oneof=24h 3d 7d 30d permanent"`
	Columns   []string `json:"columns"`
}

type ShareRead struct {
	Token     string              `json:"token"`
	ShareType string              `json:"share_type"`
	ItemCount int                 `json:"item_count"`
	ExpiresAt *serialize.UTCZTime `json:"expires_at"`
	CreatedAt serialize.UTCZTime  `json:"created_at"`
	Columns   []string            `json:"columns"`
}

type ShareListRead struct {
	Token         string              `json:"token"`
	ShareType     string              `json:"share_type"`
	ItemCount     int                 `json:"item_count"`
	ExpiresAt     *serialize.UTCZTime `json:"expires_at"`
	CreatedAt     serialize.UTCZTime  `json:"created_at"`
	CreatedBy     *int64              `json:"created_by"`
	CreatedByName *string             `json:"created_by_name"`
	Columns       []string            `json:"columns"`
}

type ShareUpdateRequest struct {
	ExpiresIn *string  `json:"expires_in" binding:"omitempty,oneof=24h 3d 7d 30d permanent"`
	Columns   []string `json:"columns"`
}

type SharePublicView struct {
	ShareType string   `json:"share_type"`
	Columns   []string `json:"columns"`
	Items     []any    `json:"items"`
}

// ============ 申购记录同步 ============

type PurchaseRecordSyncTargetRead struct {
	TraceNo     string `json:"trace_no"`
	TargetCount int    `json:"target_count"`
	CursorID    int64  `json:"cursor_id"`
}

type PurchaseRecordSyncTargetsRead struct {
	Items      []PurchaseRecordSyncTargetRead `json:"items"`
	HasMore    bool                           `json:"has_more"`
	NextCursor int64                          `json:"next_cursor"`
}

type PurchaseRecordSyncTraceUpdate struct {
	Salesperson       *string `json:"salesperson"`
	ContractNo        *string `json:"contract_no"`
	VesselNo          *string `json:"vessel_no"`
	ConsolidationPort *string `json:"consolidation_port"`
	ConsolidationDate *string `json:"consolidation_date"`
	SailingDate       *string `json:"sailing_date"`
	Status            *string `json:"status"`
}

type PurchaseRecordSyncResultRead struct {
	AffectedHeaders int `json:"affected_headers"`
	AffectedLines   int `json:"affected_lines"`
}
