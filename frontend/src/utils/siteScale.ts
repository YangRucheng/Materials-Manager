export const SITE_SCALE_STORAGE_KEY = 'site_scale_percent'
export const DEFAULT_SITE_SCALE = 100
export const MIN_SITE_SCALE = 60
export const MAX_SITE_SCALE = 120

export function normalizeSiteScale(value: unknown): number {
  const parsed = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(parsed)) return DEFAULT_SITE_SCALE
  return Math.min(MAX_SITE_SCALE, Math.max(MIN_SITE_SCALE, Math.round(parsed)))
}

export function applySiteScale(value: unknown): number {
  const scale = normalizeSiteScale(value)
  document.documentElement.style.zoom = String(scale / 100)
  return scale
}

export function loadSiteScale(): number {
  try {
    return applySiteScale(localStorage.getItem(SITE_SCALE_STORAGE_KEY) ?? DEFAULT_SITE_SCALE)
  } catch {
    return applySiteScale(DEFAULT_SITE_SCALE)
  }
}

export function saveSiteScale(value: unknown): number {
  const scale = applySiteScale(value)
  try {
    localStorage.setItem(SITE_SCALE_STORAGE_KEY, String(scale))
  } catch {
    // 缩放仍可在当前页面生效；浏览器禁用存储时不阻断操作。
  }
  return scale
}
