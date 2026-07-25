import { h, type VNode } from 'vue'

export function renderTwoLineText(
  value: string | number | null | undefined,
  fallback = '\\',
): VNode {
  const text = value === null || value === undefined || value === '' ? fallback : String(value)
  return h(
    'div',
    { class: 'table-text-two-line', title: text === fallback ? undefined : text },
    text,
  )
}
