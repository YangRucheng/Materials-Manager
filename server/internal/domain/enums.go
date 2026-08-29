// Package domain 提供业务枚举常量（与原 Python 实现对应）。
// DB 存枚举 NAME；API 输出/入参用 VALUE（部分为中文）。
package domain

// Role 管理端角色（DB 存 NAME，与 VALUE 相同）。
const (
	RoleSuperAdmin     = "SUPER_ADMIN"
	RoleWarehouseAdmin = "WAREHOUSE_ADMIN"
	RolePurchaseAdmin  = "PURCHASE_ADMIN"
	RoleReadOnly       = "READ_ONLY"
)

// OperationType 库存业务类型。
const (
	OperationInbound  = "INBOUND"
	OperationOutbound = "OUTBOUND"
)

// SourceType 流水来源（DB 存 NAME）。
const (
	SourceManual         = "MANUAL"
	SourceMiniProgram    = "MINI_PROGRAM"
	SourceReversal       = "REVERSAL"
	SourceInitialization = "INITIALIZATION"
)

// PurchasePlanStatus 申购计划状态：DB 存 NAME，API 用 VALUE（中文）。
const (
	PlanNormal   = "NORMAL"
	PlanDeferred = "DEFERRED"
	PlanArchived = "ARCHIVED"
)

// PlanStatusValue 把计划状态 NAME 转 API VALUE（中文）。
var PlanStatusValue = map[string]string{
	PlanNormal:   "正常",
	PlanDeferred: "暂不申购",
	PlanArchived: "已归档",
}

// PlanStatusName 把计划状态 VALUE 转 DB NAME。
var PlanStatusName = map[string]string{
	"正常":   PlanNormal,
	"暂不申购": PlanDeferred,
	"已归档":  PlanArchived,
}

// MiniProgramCodeEnv 小程序码环境。
const (
	MiniCodeEnvTrial   = "trial"
	MiniCodeEnvRelease = "release"
)

// MiniProgramStockStatus 小程序库存状态。
const (
	MiniStockNormal     = "normal"
	MiniStockOutOfStock = "out_of_stock"
	MiniStockLowStock   = "low_stock"
)

// MiniProgramFeatureMode 小程序功能模式。
const (
	MiniFeatureDisabled  = "disabled"
	MiniFeatureQueryOnly = "query_only"
	MiniFeatureReadWrite = "read_write"
)

// SecondaryWarehouseMode 二级库运行模式。
const (
	WarehouseModeFull = "full"
	WarehouseModeLite = "lite"
)

// WebhookPlatform 平台。
const (
	WebhookFeishu   = "FEISHU"
	WebhookDingtalk = "DINGTALK"
)

// WebhookEventType 事件类型。
const (
	WebhookStockOutboundCreated = "stock.outbound.created"
	WebhookStockInboundCreated  = "stock.inbound.created"
	WebhookMiniProgramUserBound = "mini_program.user.bound"
)

// WebhookDeliveryStatus 投递状态。
const (
	WebhookPending   = "PENDING"
	WebhookSending   = "SENDING"
	WebhookSucceeded = "SUCCEEDED"
	WebhookFailed    = "FAILED"
)

// ExcelJobStatus 导入/导出任务状态。
const (
	JobPending   = "PENDING"
	JobRunning   = "RUNNING"
	JobSucceeded = "SUCCEEDED"
	JobFailed    = "FAILED"
)

// ShareType 分享数据类型。
const (
	SharePurchasePlan   = "purchase_plan"
	SharePurchaseRecord = "purchase_record"
)

// ShareExpiryOption 分享失效选项（VALUE→换算规则在 service 处理）。
const (
	ShareExpiry24H       = "24h"
	ShareExpiry3D        = "3d"
	ShareExpiry7D        = "7d"
	ShareExpiry30D       = "30d"
	ShareExpiryPermanent = "permanent"
)
