import type { PurchasePlanStatus } from '@/api/generated'

export const defaultPurchasePlanStatus: PurchasePlanStatus = '正常'

export const purchasePlanStatusOptions: Array<{
  label: string
  value: PurchasePlanStatus
}> = [
  { label: '正常', value: '正常' },
  { label: '暂不申购', value: '暂不申购' },
  { label: '已归档', value: '已归档' },
]

export const defaultDemandDepartment = 'HXNI 检修维护部'
export const defaultPurchaseUrgency = '正常'
export const purchaseUrgencyOptions = [
  { label: '正常', value: '正常' },
  { label: '紧急', value: '紧急' },
  { label: '非常紧急', value: '非常紧急' },
]

export const purchaseCategoryOptions = [
  { label: '工具', value: '工具' },
  { label: '消耗物资', value: '消耗物资' },
  { label: '备品备件', value: '备品备件' },
]
