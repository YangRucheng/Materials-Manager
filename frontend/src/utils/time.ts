export const formatShanghaiTime = (value?: string): string => {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

export const toIsoWithTimezone = (timestamp: number): string => {
  const date = new Date(timestamp)
  const shanghai = new Date(date.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }))
  const offsetMs = shanghai.getTime() - date.getTime()
  const adjusted = new Date(date.getTime() + offsetMs)
  const base = adjusted.toISOString().slice(0, 19)
  return `${base}+08:00`
}

export const toShanghaiDate = (timestamp: number): string => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(timestamp))
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value || ''
  return `${value('year')}-${value('month')}-${value('day')}`
}

export const dateToTimestamp = (value?: string): number =>
  value ? new Date(`${value}T00:00:00+08:00`).getTime() : Date.now()

export const formatDate = (value?: string): string => (value ? value.replace(/-/g, '/') : '—')
