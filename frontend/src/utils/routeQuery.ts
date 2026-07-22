import type { LocationQueryValue } from 'vue-router'

type RouteQueryValue = LocationQueryValue | LocationQueryValue[] | undefined

export function routeQueryString(value: RouteQueryValue): string {
  const normalized = Array.isArray(value) ? value[0] : value
  return normalized ?? ''
}

export function routeQueryPositiveInteger(value: RouteQueryValue, fallback: number): number {
  const normalized = Number(routeQueryString(value))
  return Number.isInteger(normalized) && normalized > 0 ? normalized : fallback
}

export function compactRouteQuery(
  values: Record<string, string | number | null | undefined>,
): Record<string, string> {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries(values)) {
    const normalized = typeof value === 'string' ? value.trim() : value
    if (normalized === null || normalized === undefined || normalized === '') continue
    query[key] = String(normalized)
  }
  return query
}
