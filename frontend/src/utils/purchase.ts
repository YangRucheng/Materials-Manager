export interface PurchaseLineForValidation {
  purchase_material_id: number | null
  requested_qty: string
  usage: string
  subitem_no?: string
  material?: { material_code?: string }
}

export function findUncodedLineNumbers(lines: PurchaseLineForValidation[]): number[] {
  return lines.flatMap((line, index) =>
    line.material && !line.material.material_code ? [index + 1] : [],
  )
}

export function defaultTraceNo(date = new Date()): string {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value || ''
  const two = (type: Intl.DateTimeFormatPartTypes) => value(type).padStart(2, '0')
  return `追溯-${value('year')}${two('month')}${two('day')}-${two('hour')}${two('minute')}${two('second')}`
}
