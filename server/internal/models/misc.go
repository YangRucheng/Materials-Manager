package models

import "time"

// FileObject 对应 file_object 表（图片附件）。
type FileObject struct {
	ID           string `json:"id" gorm:"primaryKey;type:varchar(36)"`
	OriginalName string `json:"original_name" gorm:"type:varchar(255);not null"`
	MimeType     string `json:"mime_type" gorm:"type:varchar(32);not null;default:image/png"`
	SizeBytes    int64  `json:"size_bytes" gorm:"type:bigint unsigned;not null"`
	Width        int    `json:"width" gorm:"not null"`
	Height       int    `json:"height" gorm:"not null"`
	SHA256       string `json:"-" gorm:"type:varchar(64);not null;index"`
	Audit
}

func (FileObject) TableName() string { return "file_object" }

// MaterialCodeLibrary 对应 material_code_library 表。
type MaterialCodeLibrary struct {
	ID           int64     `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	MaterialCode string    `json:"material_code" gorm:"type:varchar(64);not null;uniqueIndex"`
	Name         *string   `json:"name" gorm:"type:varchar(128)"`
	ModelSpec    *string   `json:"model_spec" gorm:"type:varchar(255)"`
	UnitName     string    `json:"unit_name" gorm:"type:varchar(32);not null"`
	CreatedAt    time.Time `json:"created_at" gorm:"type:datetime(6);not null"`
}

func (MaterialCodeLibrary) TableName() string { return "material_code_library" }

// ExcelImportJob 对应 excel_import_job 表。status 存枚举 NAME。
type ExcelImportJob struct {
	ID               int64      `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	ImportType       string     `json:"import_type" gorm:"type:varchar(32);not null;index:ix_excel_import_job_type_status,priority:1"`
	Status           string     `json:"status" gorm:"type:varchar(16);not null;default:PENDING;index:ix_excel_import_job_type_status,priority:2"`
	OriginalFilename string     `json:"original_filename" gorm:"type:varchar(255);not null"`
	FilePath         string     `json:"file_path" gorm:"type:varchar(500);not null"`
	Result           JSON       `json:"result"`
	ErrorCode        *string    `json:"error_code" gorm:"type:varchar(64)"`
	ErrorMessage     *string    `json:"error_message" gorm:"type:varchar(1000)"`
	CreatedBy        *int64     `json:"created_by" gorm:"type:bigint unsigned"`
	CreatedAt        time.Time  `json:"created_at" gorm:"type:datetime(6);not null"`
	StartedAt        *time.Time `json:"started_at" gorm:"type:datetime(6)"`
	FinishedAt       *time.Time `json:"finished_at" gorm:"type:datetime(6)"`
	UpdatedAt        time.Time  `json:"updated_at" gorm:"type:datetime(6);not null"`
}

func (ExcelImportJob) TableName() string { return "excel_import_job" }

// ExcelExportJob 对应 excel_export_job 表。status 存枚举 NAME。
type ExcelExportJob struct {
	ID               int64      `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	ExportType       string     `json:"export_type" gorm:"type:varchar(32);not null;index:ix_excel_export_job_type_status,priority:1"`
	Status           string     `json:"status" gorm:"type:varchar(16);not null;default:PENDING;index:ix_excel_export_job_type_status,priority:2"`
	DownloadFilename *string    `json:"download_filename" gorm:"type:varchar(255)"`
	FilePath         *string    `json:"file_path" gorm:"type:varchar(500)"`
	Params           JSON       `json:"params"`
	Result           JSON       `json:"result"`
	ErrorCode        *string    `json:"error_code" gorm:"type:varchar(64)"`
	ErrorMessage     *string    `json:"error_message" gorm:"type:varchar(1000)"`
	CreatedBy        *int64     `json:"created_by" gorm:"type:bigint unsigned"`
	CreatedAt        time.Time  `json:"created_at" gorm:"type:datetime(6);not null"`
	StartedAt        *time.Time `json:"started_at" gorm:"type:datetime(6)"`
	FinishedAt       *time.Time `json:"finished_at" gorm:"type:datetime(6)"`
	UpdatedAt        time.Time  `json:"updated_at" gorm:"type:datetime(6);not null"`
}

func (ExcelExportJob) TableName() string { return "excel_export_job" }

// ShareLink 对应 share_link 表（匿名分享链接）。
type ShareLink struct {
	ID        int64      `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	Token     string     `json:"token" gorm:"type:varchar(36);not null;uniqueIndex"`
	ShareType string     `json:"share_type" gorm:"type:varchar(32);not null;index"`
	ItemIDs   JSON       `json:"item_ids" gorm:"not null"`
	Columns   JSON       `json:"columns"`
	ExpiresAt *time.Time `json:"expires_at" gorm:"type:datetime(6);index"`
	CreatedBy *int64     `json:"created_by" gorm:"type:bigint unsigned"`
	CreatedAt time.Time  `json:"created_at" gorm:"type:datetime(6);not null"`
	UpdatedAt time.Time  `json:"updated_at" gorm:"type:datetime(6);not null"`
}

func (ShareLink) TableName() string { return "share_link" }

// HuaXingInventory 对应 huaxing_inventory 表。
type HuaXingInventory struct {
	ID                 int64      `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	FirstInboundDate   *time.Time `json:"first_inbound_date" gorm:"type:date"`
	Warehouse          *string    `json:"warehouse" gorm:"type:varchar(128)"`
	MaterialCode       *string    `json:"material_code" gorm:"type:varchar(64)"`
	Name               *string    `json:"name" gorm:"type:varchar(255)"`
	ModelSpec          *string    `json:"model_spec" gorm:"type:varchar(255)"`
	Quantity           *Decimal   `json:"quantity" gorm:"type:decimal(18,2)"`
	UnitName           *string    `json:"unit_name" gorm:"type:varchar(32)"`
	Purchaser          *string    `json:"purchaser" gorm:"type:varchar(128)"`
	PurchaseDepartment *string    `json:"purchase_department" gorm:"type:varchar(128)"`
	SubitemNoName      *string    `json:"subitem_no_name" gorm:"type:varchar(255)"`
	CreatedAt          time.Time  `json:"created_at" gorm:"type:datetime(6);not null"`
}

func (HuaXingInventory) TableName() string { return "huaxing_inventory" }

// LiteInventory 对应 lite_inventory 表（精简二级库）。
type LiteInventory struct {
	ID        int64     `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	Name      string    `json:"name" gorm:"type:varchar(128);not null"`
	ModelSpec *string   `json:"model_spec" gorm:"type:varchar(255)"`
	UnitName  *string   `json:"unit_name" gorm:"type:varchar(32)"`
	Quantity  *Decimal  `json:"quantity" gorm:"type:decimal(18,2)"`
	Remark    *string   `json:"remark" gorm:"type:varchar(1000)"`
	CreatedAt time.Time `json:"created_at" gorm:"type:datetime(6);not null"`
}

func (LiteInventory) TableName() string { return "lite_inventory" }

// WebhookChannel 对应 webhook_channel 表。
type WebhookChannel struct {
	ID                  int64  `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	Platform            string `json:"platform" gorm:"type:varchar(16);not null;uniqueIndex"`
	Enabled             bool   `json:"enabled" gorm:"type:tinyint(1);not null;default:0"`
	WebhookURLEncrypted string `json:"-" gorm:"type:varchar(2000);not null;default:''"`
	SecretEncrypted     string `json:"-" gorm:"type:varchar(2000);not null;default:''"`
	SubscribedEvents    JSON   `json:"subscribed_events" gorm:"not null"`
	Audit
}

func (WebhookChannel) TableName() string { return "webhook_channel" }

// WebhookDelivery 对应 webhook_delivery 表。status 存枚举 NAME。
type WebhookDelivery struct {
	ID              int64      `json:"id" gorm:"primaryKey;autoIncrement;type:bigint unsigned"`
	EventID         string     `json:"event_id" gorm:"type:varchar(36);not null"`
	EventType       string     `json:"event_type" gorm:"type:varchar(32);not null"`
	ChannelID       int64      `json:"channel_id" gorm:"type:bigint unsigned;not null"`
	Payload         JSON       `json:"payload" gorm:"not null"`
	Status          string     `json:"status" gorm:"type:varchar(16);not null;default:PENDING"`
	Attempts        int        `json:"attempts" gorm:"type:tinyint unsigned;not null;default:0"`
	NextRetryAt     time.Time  `json:"next_retry_at" gorm:"type:datetime(6);not null"`
	ResponseStatus  *int       `json:"response_status"`
	ResponseExcerpt *string    `json:"response_excerpt" gorm:"type:varchar(1000)"`
	LastError       *string    `json:"last_error" gorm:"type:varchar(1000)"`
	CreatedAt       time.Time  `json:"created_at" gorm:"type:datetime(6);not null"`
	UpdatedAt       time.Time  `json:"updated_at" gorm:"type:datetime(6);not null"`
	DeliveredAt     *time.Time `json:"delivered_at" gorm:"type:datetime(6)"`
}

func (WebhookDelivery) TableName() string { return "webhook_delivery" }
