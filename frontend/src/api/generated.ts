/**
 * 前端 API 契约类型层。
 *
 * 单一事实源：docs/openapi.yaml（由后端 export_openapi.py 导出）。
 * 自动生成：generated.raw.ts 由 openapi-typescript 从 openapi.yaml 生成（勿手改）。
 * 本文件：类型别名 + 前端自建视图模型。
 *  - 能一一映射到 openapi schema 的类型，直接 `export type X = components['schemas']['X']`，
 *    后端改契约后重新生成即自动同步。
 *  - 前端自建的视图模型 / 泛型 / Literal（openapi 中无对应 schema）保留手写定义。
 *
 * 生成命令：npm run generate:api（先 cd backend && python scripts/export_openapi.py 同步 yaml）
 */
import type { components } from './generated.raw'

/* ===== 类型枚举（映射自 openapi，值来自后端 domain/enums.py） ===== */
export type Role = components['schemas']['Role']
export type OperationType = components['schemas']['OperationType']
export type SourceType = components['schemas']['SourceType']
export type PurchasePlanStatus = components['schemas']['PurchasePlanStatus']
export type MiniProgramCodeEnv = components['schemas']['MiniProgramCodeEnv']
export type MiniProgramStockStatus = components['schemas']['MiniProgramStockStatus']
export type WebhookPlatform = components['schemas']['WebhookPlatform']
export type WebhookEventType = components['schemas']['WebhookEventType']

/* ===== 接口类型（映射自 openapi schema） ===== */
export type ApiError = components['schemas']['ApiError']
export type User = components['schemas']['UserRead']
export type MiniProgramIdentity = components['schemas']['MiniProgramIdentityRead']
export type MiniProgramUser = components['schemas']['MiniProgramUserRead']
export type LoginRequest = components['schemas']['LoginRequest']
export type LoginResponse = components['schemas']['LoginResponse']
export type TokenPairResponse = components['schemas']['TokenPairResponse']
export type MiniProgramLoginResponse = components['schemas']['MiniProgramLoginResponse']
export type AiSearchSettings = components['schemas']['AiSearchSettingsRead']
export type AiSearchStatus = components['schemas']['AiSearchStatusRead']
export type AiSearchTestRequest = components['schemas']['AiSearchTestRequest']
export type ImageAccelerationSettings = components['schemas']['ImageAccelerationSettingsRead']
export type MaterialCodeLibrary = components['schemas']['MaterialCodeLibraryRead']
export type FileObject = components['schemas']['FileObjectRead']
export type ReplenishmentPolicy = components['schemas']['ReplenishmentPolicyRead']
export type StockMaterial = components['schemas']['StockMaterialRead']
export type InventoryBalance = components['schemas']['InventoryBalanceRead']
export type ReplenishmentDefaults = components['schemas']['ReplenishmentDefaultsRead']
export type StockOperationLine = components['schemas']['StockOperationLineRead']
export type StockOperation = components['schemas']['StockOperationRead']
export type MiniProgramMaterial = components['schemas']['MiniProgramMaterialRead']
export type MiniProgramInventoryItem = components['schemas']['MiniProgramInventoryItemRead']
export type MiniProgramOutbound = components['schemas']['MiniProgramOutboundRead']
export type OperationUpdate = components['schemas']['OperationUpdate']
export type DashboardSummary = components['schemas']['DashboardSummaryRead']
export type PurchaseFilterOptions = components['schemas']['PurchaseFilterOptions']
export type PurchaseRecordFilterOptions = components['schemas']['PurchaseRecordFilterOptions']
export type PurchasePlanResultExportRequest =
  components['schemas']['PurchasePlanResultExportRequest']
export type PurchaseRecordResultExportRequest =
  components['schemas']['PurchaseRecordResultExportRequest']
export type PurchaseMaterial = components['schemas']['PurchaseMaterialRead']
export type PurchaseRecord = components['schemas']['PurchaseRecordRead']

/* ===== 前端自建视图模型 / 泛型 / Literal（openapi 无对应 schema，手写保留） ===== */

/** 分页包装（对应后端 Page[T] 泛型，openapi 里是 Page_Xxx_ 具体类型） */
export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

/** 用户 + 接口令牌（后端 UserApiTokenRead） */
export interface ManagedUser extends User {
  api_token: string
}

/** 小程序用户合并请求 */
export interface MiniProgramUserMergeInput {
  source_user_id: number
  source_version: number
  target_version: number
}

/** AI 搜索扩展（输入/结果） */
export interface AiSearchExpandInput {
  value: string
}
export interface AiSearchExpandResult {
  original: string
  expanded: string
}
export interface AiSearchTestResult {
  original: string
  expanded: string
}

/** AI 配置写入（版本化 PUT） */
export interface AiSearchSettingsWrite {
  endpoint: string
  api_key: string
  model: string
  enabled: boolean
  mini_program_code_env: MiniProgramCodeEnv
  mini_program_code_app_id: string
  mini_program_registration_enabled: boolean
  mini_program_new_user_enabled: boolean
  image_acceleration_server_url: string
  version: number
}

/** Webhook 渠道配置 */
export interface WebhookChannelSettings {
  platform: WebhookPlatform
  enabled: boolean
  subscribed_events: WebhookEventType[]
  webhook_url: string
  secret: string
  webhook_configured: boolean
  secret_configured: boolean
  updated_at?: string | null
  version: number
}
export interface WebhookChannelSettingsWrite {
  enabled: boolean
  webhook_url: string
  secret: string
  subscribed_events: WebhookEventType[]
  version: number
}
export interface WebhookTestInput {
  webhook_url: string
  secret: string
}
export interface WebhookTestResult {
  platform: WebhookPlatform
  success: boolean
  message: string
}

/** 物资档案导入结果 */
export interface MaterialCodeLibraryImportResult {
  imported_count: number
  blank_name_count: number
  blank_model_spec_count: number
}

/** 物资写入（version 可选，新建/更新共用） */
export interface StockMaterialWrite {
  name: string
  name_id?: string
  alias?: string
  model_spec: string
  unit_name: string
  remark?: string
  image_ids: string[]
  version?: number
}

/** 补库草稿写入 */
export interface ReplenishmentDraftWrite {
  planned_qty: string
  demand_date?: string
  actual_demand_person: string
  purchase_responsible: string
}

/** 小程序出库写入 */
export interface MiniProgramOutboundWrite {
  client_request_id: string
  material_uuid: string
  occurred_at: string
  quantity: string
  business_reason: string
  receiver_unit: string
  subitem_no: string
}

/** 出入库流水写入（新建入库/出库共用） */
export interface OperationWrite {
  client_request_id: string
  occurred_at: string
  source_type: SourceType
  business_reason: string
  receiver_unit?: string
  receiver_name?: string
  subitem_no?: string
  lines: Array<{ stock_material_id: number; quantity: string }>
}

/** 申购计划导出列（前端 UI 用 Literal） */
export type PurchasePlanResultColumn =
  | 'plan_no'
  | 'plan_date'
  | 'material_code'
  | 'category'
  | 'urgency'
  | 'demand_department'
  | 'name'
  | 'model_spec'
  | 'planned_qty'
  | 'unit_name'
  | 'actual_demand_person'
  | 'purchase_responsible'
  | 'subitem_no'
  | 'usage'

/** 申购记录导出列（前端 UI 用 Literal） */
export type PurchaseRecordResultColumn =
  | 'purchase_qty'
  | 'plan_date'
  | 'purchase_order_no'
  | 'trace_no'
  | 'contract_no'
  | 'vessel_no'
  | 'consolidation_date'
  | 'consolidation_port'
  | 'sailing_date'
  | 'category'
  | 'demand_department'
  | 'material_name'
  | 'actual_demand_person'
  | 'usage'
  | 'purchase_responsible'
  | 'salesperson'
  | 'status'
  | 'purchase_date'

/** 申购计划批量更新 */
export interface PurchaseMaterialBatchUpdate {
  materials: Array<{ id: number; version: number }>
  plan_date?: string
  category?: string | null
  urgency?: string
  demand_department?: string
  actual_demand_person?: string
  purchase_responsible?: string
  subitem_no?: string | null
  usage?: string
  status?: PurchasePlanStatus
}

/** 申购记录批量更新 */
export interface PurchaseRecordBatchUpdate {
  records: Array<{ line_id: number; version: number }>
  plan_date?: string
  purchase_order_no?: string | null
  trace_no?: string | null
  contract_no?: string | null
  vessel_no?: string | null
  consolidation_date?: string | null
  consolidation_port?: string | null
  sailing_date?: string | null
  purchase_date?: string | null
  actual_demand_person?: string
  purchase_responsible?: string
  salesperson?: string | null
  status?: string
  record_remark?: string | null
}

/** 申购计划写入（新增计划） */
export interface PurchaseMaterialWrite {
  plan_date?: string
  material_code?: string
  category?: string
  urgency?: string
  demand_department?: string
  name: string
  model_spec: string
  unit_name: string
  actual_demand_person?: string
  purchase_responsible?: string
  planned_qty: string
  usage: string
  subitem_no?: string
  remark?: string
  stock_material_id?: number
  image_ids: string[]
  status?: PurchasePlanStatus
  version?: number
}

/** 申购记录写入（新建记录） */
export interface PurchaseRecordWrite {
  plan_date: string
  material_code?: string
  category?: string
  demand_department: string
  material_name: string
  model_spec: string
  unit_name: string
  actual_demand_person: string
  purchase_responsible: string
  purchase_qty: string
  usage: string
  subitem_no?: string
  plan_remark?: string
  stock_material_id?: number
  image_ids: string[]
  purchase_order_no?: string | null
  trace_no?: string | null
  contract_no?: string | null
  vessel_no?: string | null
  consolidation_date?: string
  consolidation_port?: string | null
  sailing_date?: string
  purchase_date: string
  salesperson?: string
  status: string
  record_remark?: string
  version: number
}

/** 申购记录行（前端从 PurchaseRequest 展开的视图模型） */
export interface PurchaseRequestLine {
  id: number
  purchase_material_id: number
  material_code_snapshot?: string | null
  material_name_snapshot: string
  model_spec_snapshot: string
  unit_name_snapshot: string
  purchase_qty: string
  status: string
  usage: string
  subitem_no?: string | null
}

/** 申购记录单头（前端视图模型，聚合多条行） */
export interface PurchaseRequest {
  id: number
  purchase_order_no?: string | null
  trace_no?: string | null
  contract_no?: string | null
  vessel_no?: string | null
  consolidation_date?: string
  consolidation_port?: string | null
  sailing_date?: string
  salesperson?: string
  record_remark?: string
  purchase_date?: string
  created_at: string
  version: number
  lines: PurchaseRequestLine[]
}

/** 计划批量转入记录 */
export interface MovePurchasePlansWrite {
  purchase_order_no?: string | null
  trace_no?: string | null
  contract_no?: string | null
  vessel_no?: string | null
  consolidation_date?: string
  consolidation_port?: string | null
  sailing_date?: string
  purchase_date: string
  salesperson?: string
  status: string
  record_remark?: string
}
