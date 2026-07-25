export function normalizeBaseUrl(value: string | undefined, fallback: string): string {
  const baseUrl = value?.trim() || fallback
  return baseUrl === '/' ? baseUrl : baseUrl.replace(/\/+$/, '')
}

export function joinUrl(baseUrl: string, path: string): string {
  const normalizedBaseUrl = baseUrl === '/' ? '' : baseUrl.replace(/\/+$/, '')
  return `${normalizedBaseUrl}/${path.replace(/^\/+/, '')}`
}

function isAbsoluteOrigin(value: string): boolean {
  try {
    const url = new URL(value)
    return url.pathname === '/' && !url.search && !url.hash
  } catch {
    return false
  }
}

export function resolveApiBaseUrl(value: string | undefined): string {
  const baseUrl = normalizeBaseUrl(value, '/api/v1')
  return isAbsoluteOrigin(baseUrl) ? joinUrl(baseUrl, 'api/v1') : baseUrl
}

export function resolveImageBaseUrl(value: string | undefined, resolvedApiBaseUrl: string): string {
  if (!value?.trim()) return joinUrl(resolvedApiBaseUrl, 'files/images')
  const baseUrl = normalizeBaseUrl(value, resolvedApiBaseUrl)
  return isAbsoluteOrigin(baseUrl) ? joinUrl(baseUrl, 'api/v1/files/images') : baseUrl
}

export const apiBaseUrl = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL)
export const imageBaseUrl = resolveImageBaseUrl(import.meta.env.VITE_IMAGE_BASE_URL, apiBaseUrl)
