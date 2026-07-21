/**
 * 临时契约类型快照。OpenAPI 契约位于 docs/openapi.yaml。
 * 页面与组件只引用这里的 DTO，避免各自定义不一致的接口结构。
 */
export type Role = 'SUPER_ADMIN' | 'WAREHOUSE_ADMIN' | 'PURCHASE_ADMIN' | 'READ_ONLY'
export type OperationType = 'INBOUND' | 'OUTBOUND'
export type SourceType = 'MANUAL' | 'REVERSAL' | 'INITIALIZATION'

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
}
export interface StockMaterial {
  id: number
  name: string
  model_spec: string
  unit_id: number
  unit_name: string
  remark?: string
  enabled: boolean
  current_qty: string
  images: FileObject[]
  replenishment_policy?: ReplenishmentPolicy
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
  actual_demand_person: string
  purchase_responsible: string
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
}
export interface PurchaseRecordFilterOptions extends PurchaseFilterOptions {
  salespersons: string[]
  statuses: string[]
}
export interface PurchaseMaterial {
  id: number
  plan_no: string
  plan_date: string
  material_code?: string
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
  version?: number
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
  status: string
  material_code?: string
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
  purchase_date: string
  salesperson?: string
  status: string
  record_remark?: string
  version: number
}
export interface MovePurchasePlansWrite {
  purchase_order_no?: string | null
  trace_no?: string | null
  purchase_date: string
  salesperson?: string
  status: string
  record_remark?: string
}
