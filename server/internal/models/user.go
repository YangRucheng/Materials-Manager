package models

import "time"

// User 对应 user 表（管理端账号）。
type User struct {
	ID           int64  `json:"id" gorm:"primaryKey;autoIncrement"`
	Username     string `json:"username" gorm:"type:varchar(64);not null;uniqueIndex"`
	PasswordHash string `json:"-" gorm:"type:varchar(255);not null"`
	APITokenHash string `json:"-" gorm:"type:varchar(64);not null;uniqueIndex"`
	// APIToken 非持久化：仅在创建/重新生成时承载一次性明文返回。
	APIToken    string `json:"-" gorm:"-"`
	DisplayName string `json:"display_name" gorm:"type:varchar(128);not null"`
	Role        string `json:"role" gorm:"type:varchar(32);not null"`
	Enabled     bool   `json:"enabled" gorm:"type:tinyint(1);not null;default:1"`
	Audit
}

func (User) TableName() string { return "user" }

// MiniProgramUser 对应 mini_program_user 表。
type MiniProgramUser struct {
	ID             int64  `json:"id" gorm:"primaryKey;autoIncrement"`
	DisplayName    string `json:"display_name" gorm:"type:varchar(128);not null"`
	DepartmentName string `json:"department_name" gorm:"type:varchar(128);not null;default:华星检修维护部电气车间"`
	Enabled        bool   `json:"enabled" gorm:"type:tinyint(1);not null;default:1"`
	Audit
	Identities []MiniProgramIdentity `json:"-" gorm:"foreignKey:MiniProgramUserID"`
}

func (MiniProgramUser) TableName() string { return "mini_program_user" }

// MiniProgramIdentity 对应 mini_program_identity 表。
type MiniProgramIdentity struct {
	ID                int64  `json:"id" gorm:"primaryKey;autoIncrement"`
	MiniProgramUserID int64  `json:"mini_program_user_id" gorm:"type:bigint unsigned;not null"`
	AppID             string `json:"app_id" gorm:"type:varchar(64);not null"`
	WechatOpenid      string `json:"wechat_openid" gorm:"type:varchar(128);not null"`
	Audit
}

func (MiniProgramIdentity) TableName() string { return "mini_program_identity" }

// BusinessEventLog 对应 business_event_log 表（审计日志）。
type BusinessEventLog struct {
	ID           int64     `json:"id" gorm:"primaryKey;autoIncrement"`
	BusinessType string    `json:"business_type" gorm:"type:varchar(64);not null;index:ix_business_event_entity,priority:1"`
	BusinessID   int64     `json:"business_id" gorm:"type:bigint unsigned;not null;index:ix_business_event_entity,priority:2"`
	Action       string    `json:"action" gorm:"type:varchar(64);not null"`
	OldStatus    *string   `json:"old_status" gorm:"type:varchar(32)"`
	NewStatus    *string   `json:"new_status" gorm:"type:varchar(32)"`
	OccurredAt   time.Time `json:"occurred_at" gorm:"type:datetime;not null"`
	Remark       *string   `json:"remark" gorm:"type:varchar(1000)"`
	BeforeData   JSON      `json:"before_data"`
	AfterData    JSON      `json:"after_data"`
}

func (BusinessEventLog) TableName() string { return "business_event_log" }

// SystemSetting 对应 system_setting 表（键值配置）。
type SystemSetting struct {
	SettingKey   string    `json:"setting_key" gorm:"primaryKey;type:varchar(64)"`
	SettingValue JSON      `json:"setting_value" gorm:"not null"`
	Version      int       `json:"version" gorm:"type:int unsigned;not null;default:1"`
	UpdatedAt    time.Time `json:"updated_at" gorm:"type:datetime;not null"`
}

func (SystemSetting) TableName() string { return "system_setting" }
