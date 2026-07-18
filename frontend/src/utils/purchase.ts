export interface PurchaseLineForValidation {
  purchase_material_id: number | null
  requested_qty: string
  usage: string
  project_subitem_id: number | null
  material?: { material_code?: string }
}

export function findUncodedLineNumbers(lines: PurchaseLineForValidation[]): number[] {
  return lines.flatMap((line, index) =>
    line.material && !line.material.material_code ? [index + 1] : [],
  )
}

export function defaultPurchaseRequestNo(date = new Date()): string {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  }).formatToParts(date)
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value || ''
  return `申购单-${value('year')}年${value('month')}月${value('day')}日`
}
