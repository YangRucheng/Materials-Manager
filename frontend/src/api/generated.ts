/**
 * 临时契约类型快照。OpenAPI 契约位于 docs/openapi.yaml。
 * 页面与组件只引用这里的 DTO，避免各自定义不一致的接口结构。
 */
export type Role = 'SUPER_ADMIN' | 'WAREHOUSE_ADMIN' | 'PURCHASE_ADMIN' | 'READ_ONLY'
export type PurchaseRequestStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'PROCESSING'
  | 'RETURNED'
  | 'PARTIALLY_RECEIVED'
  | 'COMPLETED'
  | 'CLOSED'
  | 'CANCELED'
export type OperationType = 'INBOUND' | 'OUTBOUND'
export type SourceType = 'MANUAL' | 'PURCHASE_RECEIPT' | 'REVERSAL' | 'INITIALIZATION'

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
  url: string
  mime_type: 'image/png'
  size_bytes: number
  width: number
  height: number
}
export interface ReplenishmentPolicy {
  minimum_qty: string
  target_qty: string
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
  target_qty?: string
  on_order_qty: string
  is_low_stock: boolean
  warning_state?: 'PENDING_PURCHASE' | 'ON_ORDER'
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
  purchase_request_line_id?: number
}
export interface StockOperation {
  id: number
  operation_no: string
  operation_type: OperationType
  occurred_at: string
  operator_name: string
  business_reason: string
  receiver_name?: string
  subitem_no?: string
  source_type: SourceType
  reversal_of_id?: number
  purchase_request_no?: string
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
  lines: Array<{ stock_material_id: number; quantity: string; purchase_request_line_id?: number }>
}
export interface OperationUpdate {
  version: number
  operation_type: OperationType
  occurred_at: string
  source_type: SourceType
  business_reason: string
  receiver_name?: string
  subitem_no?: string
  lines: Array<{ stock_material_id: number; quantity: string; purchase_request_line_id?: number }>
}
export interface DashboardSummary {
  stock_material_count: number
  low_stock_count: number
  pending_purchase_count: number
  on_order_count: number
  uncoded_purchase_material_count: number
  pending_purchase_request_count: number
  partially_received_count: number
}
export interface PurchaseMaterial {
  id: number
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
export interface BusinessEvent {
  id: number
  action: string
  old_status?: string
  new_status?: string
  operator_name: string
  occurred_at: string
  remark?: string
}
export interface PurchaseRequestLine {
  id: number
  purchase_material_id: number
  material_code_snapshot?: string
  material_name_snapshot: string
  model_spec_snapshot: string
  unit_name_snapshot: string
  requested_qty: string
  received_qty: string
  usage: string
  subitem_no?: string
}
export interface PurchaseRequest {
  id: number
  purchase_order_no?: string | null
  trace_no?: string | null
  status: PurchaseRequestStatus
  applicant_name: string
  handler_name?: string
  salesperson?: string
  remark?: string
  return_reason?: string
  close_reason?: string
  purchase_date?: string
  completed_at?: string
  created_at: string
  version: number
  lines: PurchaseRequestLine[]
  events: BusinessEvent[]
}
export interface PurchaseRecord {
  line_id: number
  purchase_request_id: number
  purchase_material_id: number
  purchase_order_no?: string | null
  trace_no?: string | null
  status: PurchaseRequestStatus
  material_code: string
  material_name: string
  model_spec: string
  unit_name: string
  planned_qty: string
  received_qty: string
  remaining_qty: string
  actual_demand_person: string
  purchase_responsible: string
  salesperson?: string
  remark?: string
  usage: string
  subitem_no?: string
  stock_material_id?: number
  purchase_date?: string
  created_at: string
  version: number
}
export interface PurchaseRequestWrite {
  purchase_order_no?: string | null
  trace_no?: string | null
  purchase_date?: string
  remark?: string
  version?: number
  lines: Array<{
    id?: number
    purchase_material_id: number | null
    requested_qty: string
    usage: string
    subitem_no?: string
  }>
}
export interface MovePurchasePlansWrite {
  purchase_order_no?: string | null
  trace_no?: string | null
  purchase_date: string
  salesperson?: string
  remark?: string
}
export interface PreparedInbound {
  purchase_request_no?: string
  line_id: number
  purchase_material_id: number
  material_name: string
  model_spec: string
  unit_name: string
  remaining_qty: string
  stock_material_id?: number
}
