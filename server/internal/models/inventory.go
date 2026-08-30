package models

import "time"

// StockMaterial 对应 stock_material 表（二级库物资）。
type StockMaterial struct {
	ID           int64   `json:"id" gorm:"primaryKey;autoIncrement"`
	UUID         string  `json:"uuid" gorm:"type:varchar(36);not null;uniqueIndex"`
	Name         string  `json:"name" gorm:"type:varchar(128);not null"`
	NameID       *string `json:"name_id" gorm:"type:varchar(128)"`
	Alias        *string `json:"alias" gorm:"type:varchar(128)"`
	ModelSpec    string  `json:"model_spec" gorm:"type:varchar(255);not null"`
	UnitName     string  `json:"unit_name" gorm:"type:varchar(32);not null"`
	Remark       *string `json:"remark" gorm:"type:varchar(1000)"`
	IdentityHash string  `json:"-" gorm:"type:varchar(64);not null;uniqueIndex"`
	Audit

	Balance             *StockBalance             `json:"-" gorm:"foreignKey:StockMaterialID"`
	ReplenishmentPolicy *StockReplenishmentPolicy `json:"-" gorm:"foreignKey:StockMaterialID"`
	Images              []StockMaterialImage      `json:"-" gorm:"foreignKey:MaterialID"`
}

func (StockMaterial) TableName() string { return "stock_material" }

// StockMaterialImage 对应 stock_material_image 表。
type StockMaterialImage struct {
	MaterialID int64  `json:"material_id" gorm:"primaryKey;type:bigint unsigned"`
	FileID     string `json:"file_id" gorm:"primaryKey;type:varchar(36)"`
	SortOrder  int    `json:"sort_order" gorm:"type:tinyint unsigned;not null;default:0"`
}

func (StockMaterialImage) TableName() string { return "stock_material_image" }

// StockBalance 对应 stock_balance 表。
type StockBalance struct {
	StockMaterialID int64     `json:"stock_material_id" gorm:"primaryKey;type:bigint unsigned"`
	Quantity        Decimal   `json:"quantity" gorm:"type:decimal(18,1);not null;default:0"`
	Version         int       `json:"version" gorm:"type:int unsigned;not null;default:1"`
	UpdatedAt       time.Time `json:"updated_at" gorm:"type:datetime;not null"`
}

func (StockBalance) TableName() string { return "stock_balance" }

// StockReplenishmentPolicy 对应 stock_replenishment_policy 表（安全库存）。
type StockReplenishmentPolicy struct {
	StockMaterialID int64     `json:"stock_material_id" gorm:"primaryKey;type:bigint unsigned"`
	MinimumQty      Decimal   `json:"minimum_qty" gorm:"type:decimal(18,1);not null"`
	Enabled         bool      `json:"enabled" gorm:"type:tinyint(1);not null;default:1"`
	CreatedAt       time.Time `json:"created_at" gorm:"type:datetime;not null"`
	UpdatedAt       time.Time `json:"updated_at" gorm:"type:datetime;not null"`
	Version         int       `json:"version" gorm:"type:int unsigned;not null;default:1"`
}

func (StockReplenishmentPolicy) TableName() string { return "stock_replenishment_policy" }

// StockOperation 对应 stock_operation 表（库存流水）。operation_type/source_type 存枚举 NAME。
type StockOperation struct {
	ID                          int64     `json:"id" gorm:"primaryKey;autoIncrement"`
	OperationNo                 string    `json:"operation_no" gorm:"type:varchar(32);not null;uniqueIndex"`
	OperationType               string    `json:"operation_type" gorm:"type:varchar(16);not null"`
	OccurredAt                  time.Time `json:"occurred_at" gorm:"type:datetime;not null"`
	BusinessReason              string    `json:"business_reason" gorm:"type:varchar(500);not null"`
	ReceiverUnit                *string   `json:"receiver_unit" gorm:"type:varchar(128)"`
	ReceiverName                *string   `json:"receiver_name" gorm:"type:varchar(64)"`
	SubitemNo                   *string   `json:"subitem_no" gorm:"type:varchar(64)"`
	SourceType                  string    `json:"source_type" gorm:"type:varchar(16);not null"`
	ReversalOfID                *int64    `json:"reversal_of_id" gorm:"type:bigint unsigned"`
	ClientRequestID             string    `json:"client_request_id" gorm:"type:varchar(64);not null;uniqueIndex"`
	MiniProgramUserNameSnapshot *string   `json:"mini_program_user_name_snapshot" gorm:"type:varchar(128)"`
	Audit

	Lines []StockOperationLine `json:"-" gorm:"foreignKey:OperationID"`
}

func (StockOperation) TableName() string { return "stock_operation" }

// StockOperationLine 对应 stock_operation_line 表。
type StockOperationLine struct {
	ID                   int64   `json:"id" gorm:"primaryKey;autoIncrement"`
	OperationID          int64   `json:"operation_id" gorm:"type:bigint unsigned;not null"`
	StockMaterialID      int64   `json:"stock_material_id" gorm:"type:bigint unsigned;not null"`
	Quantity             Decimal `json:"quantity" gorm:"type:decimal(18,1);not null"`
	RemainingQty         Decimal `json:"remaining_qty" gorm:"type:decimal(18,1);not null"`
	BeforeQty            Decimal `json:"before_qty" gorm:"type:decimal(18,1);not null"`
	AfterQty             Decimal `json:"after_qty" gorm:"type:decimal(18,1);not null"`
	MaterialNameSnapshot string  `json:"material_name_snapshot" gorm:"type:varchar(128);not null"`
	ModelSpecSnapshot    string  `json:"model_spec_snapshot" gorm:"type:varchar(255);not null"`
	UnitNameSnapshot     string  `json:"unit_name_snapshot" gorm:"type:varchar(32);not null"`
	Audit
}

func (StockOperationLine) TableName() string { return "stock_operation_line" }
