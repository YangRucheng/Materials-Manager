const LAST_PURCHASE_RESPONSIBLE_KEY = 'procurement.purchase-materials.last-purchase-responsible'

export function defaultPurchaseOrderNo(date = new Date()): string {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  }).formatToParts(date)
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value || ''
  return `申购 ${value('year')}/${value('month')}/${value('day')}`
}

export function getLastPurchaseResponsible(): string {
  return localStorage.getItem(LAST_PURCHASE_RESPONSIBLE_KEY)?.trim() || ''
}

export function rememberPurchaseResponsible(value: string): void {
  const responsible = value.trim()
  if (responsible) localStorage.setItem(LAST_PURCHASE_RESPONSIBLE_KEY, responsible)
}
