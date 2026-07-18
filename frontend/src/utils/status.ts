import type { PurchaseRequestStatus } from '@/api/generated'
export const requestStatusLabels: Record<PurchaseRequestStatus, string> = {
  DRAFT: '草稿',
  SUBMITTED: '已提交',
  PROCESSING: '处理中',
  RETURNED: '已退回',
  PARTIALLY_RECEIVED: '部分到货',
  COMPLETED: '已完成',
  CLOSED: '已关闭',
  CANCELED: '已取消',
}
export const statusTagType = (
  status: string,
): 'default' | 'success' | 'warning' | 'error' | 'info' => {
  if (['COMPLETED'].includes(status)) return 'success'
  if (['RETURNED', 'PARTIALLY_RECEIVED'].includes(status)) return 'warning'
  if (['REJECTED', 'CANCELED', 'CLOSED'].includes(status)) return 'error'
  if (['SUBMITTED', 'PROCESSING'].includes(status)) return 'info'
  return 'default'
}
