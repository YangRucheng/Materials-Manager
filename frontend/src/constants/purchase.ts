import type { PurchasePlanStatus } from '@/api/generated'

export const defaultPurchasePlanStatus: PurchasePlanStatus = '正常'

export const purchasePlanStatusOptions: Array<{
  label: string
  value: PurchasePlanStatus
}> = [
  { label: '正常', value: '正常' },
  { label: '已归档', value: '已归档' },
]

export type PurchasePlanStatusFilter = PurchasePlanStatus | '全部'

export const purchasePlanStatusFilterOptions: Array<{
  label: string
  value: PurchasePlanStatusFilter
}> = [...purchasePlanStatusOptions, { label: '全部状态', value: '全部' }]
