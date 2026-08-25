/**
 * 分享页可展示列定义：键名与后端 SharePlanColumn / ShareRecordColumn Literal 严格一致，
 * 供分享页（ShareView）渲染注册表与管理页（ShareLinksView）勾选列表共用，避免两处漂移。
 */

export interface ShareColumnOption {
  key: string
  label: string
}

export const SHARE_PLAN_COLUMNS: ShareColumnOption[] = [
  { key: 'plan_date', label: '需求日期' },
  { key: 'material_code', label: '物料编码' },
  { key: 'category', label: '类别' },
  { key: 'urgency', label: '紧急程度' },
  { key: 'demand_department', label: '需求部门' },
  { key: 'name', label: '名称' },
  { key: 'model_spec', label: '型号规格' },
  { key: 'planned_qty', label: '计划数量' },
  { key: 'actual_demand_person', label: '提报员工' },
  { key: 'purchase_responsible', label: '实际需求人' },
  { key: 'subitem_no', label: '子项号' },
  { key: 'usage', label: '用途' },
  { key: 'status', label: '状态' },
  { key: 'images', label: '图片' },
]

export const SHARE_RECORD_COLUMNS: ShareColumnOption[] = [
  { key: 'plan_date', label: '需求日期' },
  { key: 'purchase_order_no', label: '申购单号' },
  { key: 'trace_no', label: '追溯号' },
  { key: 'category', label: '类别' },
  { key: 'demand_department', label: '需求部门' },
  { key: 'material_name', label: '物资名称' },
  { key: 'model_spec', label: '型号规格' },
  { key: 'purchase_qty', label: '申购数量' },
  { key: 'actual_demand_person', label: '提报员工' },
  { key: 'purchase_responsible', label: '实际需求人' },
  { key: 'salesperson', label: '业务员' },
  { key: 'subitem_no', label: '子项号' },
  { key: 'usage', label: '用途' },
  { key: 'status', label: '状态' },
  { key: 'images', label: '图片' },
]

/** 按分享类型取可展示列定义。 */
export function shareColumnOptions(
  shareType: 'purchase_plan' | 'purchase_record',
): ShareColumnOption[] {
  return shareType === 'purchase_record' ? SHARE_RECORD_COLUMNS : SHARE_PLAN_COLUMNS
}

/** 默认不展示的列：分享链接默认不对外展示「状态」。 */
export const SHARE_DEFAULT_HIDDEN_KEYS: readonly string[] = ['status']

/** 分享链接默认展示列 = 该类型全部列去掉默认隐藏列。 */
export function defaultShareColumnKeys(shareType: 'purchase_plan' | 'purchase_record'): string[] {
  const hidden = new Set(SHARE_DEFAULT_HIDDEN_KEYS)
  return shareColumnOptions(shareType)
    .map((option) => option.key)
    .filter((key) => !hidden.has(key))
}
