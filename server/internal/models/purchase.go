package models

import "time"

// PurchaseMaterial 对应 purchase_material 表（申购计划）。status 存枚举 NAME（NORMAL/DEFERRED/ARCHIVED）。
type PurchaseMaterial struct {
	ID                  int64     `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	PlanNo              string    `json:"plan_no" gorm:"type:varchar(32);not null;uniqueIndex"`
	PlanDate            time.Time `json:"plan_date" gorm:"type:date;not null"`
	MaterialCode        *string   `json:"material_code" gorm:"type:varchar(64)"`
	Category            *string   `json:"category" gorm:"type:varchar(64)"`
	Urgency             string    `json:"urgency" gorm:"type:varchar(32);not null;default:正常"`
	DemandDepartment    string    `json:"demand_department" gorm:"type:varchar(128);not null;default:HXNI 检修维护部"`
	Name                string    `json:"name" gorm:"type:varchar(128);not null"`
	ModelSpec           string    `json:"model_spec" gorm:"type:varchar(255);not null"`
	UnitName            string    `json:"unit_name" gorm:"type:varchar(32);not null"`
	ActualDemandPerson  string    `json:"actual_demand_person" gorm:"type:varchar(128);not null"`
	PurchaseResponsible string    `json:"purchase_responsible" gorm:"type:varchar(128);not null"`
	PlannedQty          Decimal   `json:"planned_qty" gorm:"type:decimal(18,1);not null"`
	Usage               string    `json:"usage" gorm:"type:varchar(500);not null"`
	SubitemNo           *string   `json:"subitem_no" gorm:"type:varchar(64)"`
	Remark              *string   `json:"remark" gorm:"type:varchar(1000)"`
	StockMaterialID     *int64    `json:"stock_material_id" gorm:"type:bigint unsigned;index"`
	Status              string    `json:"status" gorm:"type:varchar(16);not null;default:NORMAL;index"`
	Audit

	StockMaterial *StockMaterial          `json:"-" gorm:"foreignKey:StockMaterialID"`
	Images        []PurchaseMaterialImage `json:"-" gorm:"foreignKey:MaterialID"`
}

func (PurchaseMaterial) TableName() string { return "purchase_material" }

// PurchaseMaterialImage 对应 purchase_material_image 表。
type PurchaseMaterialImage struct {
	MaterialID int64  `json:"material_id" gorm:"primaryKey;type:bigint unsigned"`
	FileID     string `json:"file_id" gorm:"primaryKey;type:varchar(36)"`
	SortOrder  int    `json:"sort_order" gorm:"type:tinyint unsigned;not null;default:0"`
}

func (PurchaseMaterialImage) TableName() string { return "purchase_material_image" }

// PurchasePlanTemplate 对应 purchase_plan_template 表（周期性计划）。
type PurchasePlanTemplate struct {
	ID                  int64   `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	MaterialCode        *string `json:"material_code" gorm:"type:varchar(64)"`
	Category            *string `json:"category" gorm:"type:varchar(64)"`
	Urgency             string  `json:"urgency" gorm:"type:varchar(32);not null;default:正常"`
	DemandDepartment    string  `json:"demand_department" gorm:"type:varchar(128);not null;default:HXNI 检修维护部"`
	Name                string  `json:"name" gorm:"type:varchar(128);not null"`
	ModelSpec           string  `json:"model_spec" gorm:"type:varchar(255);not null"`
	UnitName            string  `json:"unit_name" gorm:"type:varchar(32);not null"`
	ActualDemandPerson  string  `json:"actual_demand_person" gorm:"type:varchar(128);not null"`
	PurchaseResponsible string  `json:"purchase_responsible" gorm:"type:varchar(128);not null"`
	PlannedQty          Decimal `json:"planned_qty" gorm:"type:decimal(18,1);not null"`
	Usage               string  `json:"usage" gorm:"type:varchar(500);not null"`
	SubitemNo           *string `json:"subitem_no" gorm:"type:varchar(64)"`
	Remark              *string `json:"remark" gorm:"type:varchar(1000)"`
	StockMaterialID     *int64  `json:"stock_material_id" gorm:"type:bigint unsigned;index"`
	Audit

	StockMaterial *StockMaterial              `json:"-" gorm:"foreignKey:StockMaterialID"`
	Images        []PurchasePlanTemplateImage `json:"-" gorm:"foreignKey:PlanID"`
}

func (PurchasePlanTemplate) TableName() string { return "purchase_plan_template" }

// PurchasePlanTemplateImage 对应 purchase_plan_template_image 表。
type PurchasePlanTemplateImage struct {
	PlanID    int64  `json:"plan_id" gorm:"primaryKey;type:bigint unsigned"`
	FileID    string `json:"file_id" gorm:"primaryKey;type:varchar(36)"`
	SortOrder int    `json:"sort_order" gorm:"type:tinyint unsigned;not null;default:0"`
}

func (PurchasePlanTemplateImage) TableName() string { return "purchase_plan_template_image" }

// PurchaseRequest 对应 purchase_request 表（申购记录头部）。
type PurchaseRequest struct {
	ID                int64      `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	PurchaseOrderNo   *string    `json:"purchase_order_no" gorm:"type:varchar(128)"`
	ContractNo        *string    `json:"contract_no" gorm:"type:varchar(128)"`
	VesselNo          *string    `json:"vessel_no" gorm:"type:varchar(128)"`
	ConsolidationDate *time.Time `json:"consolidation_date" gorm:"type:date"`
	ConsolidationPort *string    `json:"consolidation_port" gorm:"type:varchar(128)"`
	SailingDate       *time.Time `json:"sailing_date" gorm:"type:date"`
	Remark            *string    `json:"remark" gorm:"type:varchar(1000)"`
	PurchaseDate      *time.Time `json:"purchase_date" gorm:"type:date"`
	Audit

	Lines []PurchaseRequestLine `json:"-" gorm:"foreignKey:PurchaseRequestID"`
}

func (PurchaseRequest) TableName() string { return "purchase_request" }

// PurchaseRequestLine 对应 purchase_request_line 表（申购记录行，自包含快照）。
type PurchaseRequestLine struct {
	ID                          int64     `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	PurchaseRequestID           int64     `json:"purchase_request_id" gorm:"type:bigint unsigned;not null"`
	PurchaseMaterialID          *int64    `json:"purchase_material_id" gorm:"type:bigint unsigned"`
	PlanNoSnapshot              string    `json:"plan_no_snapshot" gorm:"type:varchar(32);not null"`
	PlanDateSnapshot            time.Time `json:"plan_date_snapshot" gorm:"type:date;not null"`
	MaterialCodeSnapshot        *string   `json:"material_code_snapshot" gorm:"type:varchar(64)"`
	CategorySnapshot            *string   `json:"category_snapshot" gorm:"type:varchar(64)"`
	DemandDepartmentSnapshot    string    `json:"demand_department_snapshot" gorm:"type:varchar(128);not null"`
	MaterialNameSnapshot        string    `json:"material_name_snapshot" gorm:"type:varchar(128);not null"`
	ModelSpecSnapshot           string    `json:"model_spec_snapshot" gorm:"type:varchar(255);not null"`
	UnitNameSnapshot            string    `json:"unit_name_snapshot" gorm:"type:varchar(32);not null"`
	ActualDemandPersonSnapshot  string    `json:"actual_demand_person_snapshot" gorm:"type:varchar(128);not null"`
	PurchaseResponsibleSnapshot string    `json:"purchase_responsible_snapshot" gorm:"type:varchar(128);not null"`
	PlanRemarkSnapshot          *string   `json:"plan_remark_snapshot" gorm:"type:varchar(1000)"`
	StockMaterialIDSnapshot     *int64    `json:"stock_material_id_snapshot" gorm:"type:bigint unsigned"`
	PurchaseQty                 Decimal   `json:"purchase_qty" gorm:"type:decimal(18,1);not null"`
	Status                      string    `json:"status" gorm:"type:varchar(128);not null;default:已申购"`
	Usage                       string    `json:"usage" gorm:"type:varchar(500);not null"`
	UsageHash                   string    `json:"-" gorm:"type:varchar(32);not null"`
	SubitemNo                   *string   `json:"subitem_no" gorm:"type:varchar(64)"`
	TraceNo                     *string   `json:"trace_no" gorm:"type:varchar(128);index"`
	Salesperson                 *string   `json:"salesperson" gorm:"type:varchar(128)"`
	Audit

	Request          *PurchaseRequest           `json:"-" gorm:"foreignKey:PurchaseRequestID"`
	PurchaseMaterial *PurchaseMaterial          `json:"-" gorm:"foreignKey:PurchaseMaterialID"`
	Images           []PurchaseRequestLineImage `json:"-" gorm:"foreignKey:LineID"`
}

func (PurchaseRequestLine) TableName() string { return "purchase_request_line" }

// PurchaseRequestLineImage 对应 purchase_request_line_image 表。
type PurchaseRequestLineImage struct {
	LineID    int64  `json:"line_id" gorm:"primaryKey;type:bigint unsigned"`
	FileID    string `json:"file_id" gorm:"primaryKey;type:varchar(36)"`
	SortOrder int    `json:"sort_order" gorm:"type:tinyint unsigned;not null;default:0"`
}

func (PurchaseRequestLineImage) TableName() string { return "purchase_request_line_image" }
