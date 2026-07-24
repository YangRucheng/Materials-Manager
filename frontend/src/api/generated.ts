/**
 * 临时契约类型快照。OpenAPI 契约位于 docs/openapi.yaml。
 * 页面与组件只引用这里的 DTO，避免各自定义不一致的接口结构。
 */
export type Role = 'SUPER_ADMIN' | 'WAREHOUSE_ADMIN' | 'PURCHASE_ADMIN' | 'READ_ONLY'
export type OperationType = 'INBOUND' | 'OUTBOUND'
export type SourceType = 'MANUAL' | 'REVERSAL' | 'INITIALIZATION'
export type PurchasePlanStatus = '正常' | '暂不申购' | '已归档'

export interface ApiError {
  code: string
  message: string
  details?: Record<string, unknown>
  request_id?: string
}
export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}
export interface User {
  id: number
  username: string
  display_name: string
  role: Role
  enabled: boolean
  version: number
}
export interface LoginRequest {
  username: string
  password: string
}
export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  user: User
}
export interface AiSearchSettings {
  endpoint: string
  api_key: string
  model: string
  enabled: boolean
  updated_at?: string
  version: number
}
export interface AiSearchSettingsWrite {
  endpoint: string
  api_key: string
  model: string
  enabled: boolean
  version: number
}
export interface AiSearchStatus {
  available: boolean
}
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
export interface MeasurementUnit {
  id: number
  code: string
  name: string
  decimal_places: 0 | 1
  enabled: boolean
  version: number
}
export interface FileObject {
  id: string
  original_name: string
  mime_type: 'image/png'
  size_bytes: number
  width: number
  height: number
}
export interface ReplenishmentPolicy {
  minimum_qty: string
  enabled: boolean
  version: number
}
export interface StockMaterial {
  id: number
  name: string
  model_spec: string
  unit_id: number
  unit_name: string
  remark?: string
  current_qty: string
  images: FileObject[]
  replenishment_policy?: ReplenishmentPolicy
  has_operation_records: boolean
  created_at: string
  updated_at: string
  version: number
}
export interface StockMaterialWrite {
  name: string
  model_spec: string
  unit_id: number | null
  remark?: string
  image_ids: string[]
  version?: number
}
export interface InventoryBalance {
  stock_material_id: number
  name: string
  model_spec: string
  unit_name: string
  decimal_places: number
  current_qty: string
  minimum_qty?: string
  is_low_stock: boolean
  suggested_purchase_qty: string
  updated_at: string
}
export interface ReplenishmentDraftWrite {
  planned_qty: string
  demand_date?: string
  actual_demand_person: string
  purchase_responsible: string
}
export interface ReplenishmentDefaults {
  purchase_responsible: string
  demand_date: string
}
export interface StockOperationLine {
  id?: number
  stock_material_id: number
  material_name: string
  model_spec: string
  unit_name: string
  quantity: string
  before_qty: string
  after_qty: string
}
export interface StockOperation {
  id: number
  operation_no: string
  operation_type: OperationType
  occurred_at: string
  business_reason: string
  receiver_unit?: string
  receiver_name?: string
  subitem_no?: string
  source_type: SourceType
  reversal_of_id?: number
  client_request_id: string
  lines: StockOperationLine[]
  created_at: string
  version: number
}
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
export interface OperationUpdate {
  version: number
  operation_type: OperationType
  occurred_at: string
  source_type: SourceType
  business_reason: string
  receiver_unit?: string
  receiver_name?: string
  subitem_no?: string
  lines: Array<{ stock_material_id: number; quantity: string }>
}
export interface DashboardSummary {
  stock_material_count: number
  low_stock_count: number
  uncoded_purchase_material_count: number
  purchase_record_count: number
}
export interface PurchaseFilterOptions {
  actual_demand_persons: string[]
  purchase_responsibles: string[]
  subitem_nos: string[]
  categories: string[]
}
export interface PurchaseRecordFilterOptions extends PurchaseFilterOptions {
  salespersons: string[]
  statuses: string[]
}
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
export interface PurchasePlanResultExportRequest {
  columns: PurchasePlanResultColumn[]
  name?: string
  model_spec?: string
  actual_demand_person?: string
  empty_actual_demand_person: boolean
  subitem_no?: string
  empty_subitem_no: boolean
  status?: PurchasePlanStatus[]
  category?: string
}
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
  | 'purchase_responsible'
  | 'salesperson'
  | 'status'
  | 'purchase_date'
export interface PurchaseRecordResultExportRequest {
  columns: PurchaseRecordResultColumn[]
  purchase_order_no?: string
  trace_no?: string
  category?: string
  name?: string
  model_spec?: string
  purchase_responsible?: string
  salesperson?: string
  status?: string
  empty_status: boolean
}
export interface PurchaseMaterial {
  id: number
  plan_no: string
  plan_date: string
  material_code?: string
  category?: string
  urgency: string
  demand_department: string
  name: string
  model_spec: string
  unit_id: number
  unit_name: string
  actual_demand_person: string
  purchase_responsible: string
  planned_qty: string
  usage: string
  subitem_no?: string
  remark?: string
  stock_material_id?: number
  stock_material_name?: string
  status: PurchasePlanStatus
  moved_to_record: boolean
  enabled: boolean
  images: FileObject[]
  created_at: string
  updated_at: string
  version: number
}
export interface PurchaseMaterialWrite {
  plan_date?: string
  material_code?: string
  category?: string
  urgency?: string
  demand_department?: string
  name: string
  model_spec: string
  unit_id: number | null
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
export interface PurchaseMaterialBatchUpdate {
  materials: Array<{ id: number; version: number }>
  plan_date?: string
  category?: string | null
  demand_department?: string
  actual_demand_person?: string
  subitem_no?: string | null
  usage?: string
  status?: PurchasePlanStatus
}
export interface PurchaseRequestLine {
  id: number
  purchase_material_id: number
  material_code_snapshot?: string
  material_name_snapshot: string
  model_spec_snapshot: string
  unit_name_snapshot: string
  purchase_qty: string
  status: string
  usage: string
  subitem_no?: string
}
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
export interface PurchaseRecord {
  line_id: number
  purchase_request_id: number
  purchase_material_id: number
  plan_no: string
  plan_date: string
  purchase_order_no?: string | null
  trace_no?: string | null
  contract_no?: string | null
  vessel_no?: string | null
  consolidation_date?: string
  consolidation_port?: string | null
  sailing_date?: string
  status: string
  material_code?: string
  category?: string
  demand_department: string
  material_name: string
  model_spec: string
  unit_id: number
  unit_name: string
  purchase_qty: string
  actual_demand_person: string
  purchase_responsible: string
  salesperson?: string
  plan_remark?: string
  record_remark?: string
  usage: string
  subitem_no?: string
  images: FileObject[]
  stock_material_id?: number
  purchase_date?: string
  created_at: string
  updated_at: string
  version: number
}
export interface PurchaseRecordWrite {
  plan_date: string
  material_code?: string
  category?: string
  demand_department: string
  material_name: string
  model_spec: string
  unit_id: number | null
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
