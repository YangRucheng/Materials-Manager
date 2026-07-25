export function normalizeBaseUrl(value: string | undefined, fallback: string): string {
  const baseUrl = value?.trim() || fallback
  return baseUrl === '/' ? baseUrl : baseUrl.replace(/\/+$/, '')
}

export function joinUrl(baseUrl: string, path: string): string {
  const normalizedBaseUrl = baseUrl === '/' ? '' : baseUrl.replace(/\/+$/, '')
  return `${normalizedBaseUrl}/${path.replace(/^\/+/, '')}`
}

export const apiBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL, '/api/v1')
export const imageBaseUrl = normalizeBaseUrl(
  import.meta.env.VITE_IMAGE_BASE_URL,
  joinUrl(apiBaseUrl, 'files/images'),
)
