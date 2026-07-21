const INTERACTIVE_SELECTOR = [
  'a',
  'button',
  'input',
  'select',
  'textarea',
  'label',
  '[role="button"]',
  '[role="link"]',
  '[contenteditable="true"]',
  '[data-row-click-ignore]',
  '.n-checkbox',
  '.n-data-table-td--selection',
].join(', ')

const DRAG_THRESHOLD_PX = 4

function hasSelectedTextWithin(element: Element | null): boolean {
  const selection = window.getSelection()
  if (!element || !selection || selection.isCollapsed || !selection.toString().trim()) {
    return false
  }

  for (let index = 0; index < selection.rangeCount; index += 1) {
    try {
      if (selection.getRangeAt(index).intersectsNode(element)) {
        return true
      }
    } catch {
      return false
    }
  }
  return false
}

export function createTableRowClickGuard() {
  let pointerStart: { x: number; y: number } | null = null

  return {
    onMouseDown(event: MouseEvent) {
      pointerStart = event.button === 0 ? { x: event.clientX, y: event.clientY } : null
    },
    shouldIgnore(event: MouseEvent): boolean {
      const start = pointerStart
      pointerStart = null

      const target = event.target
      if (target instanceof Element && target.closest(INTERACTIVE_SELECTOR)) {
        return true
      }

      if (
        start &&
        Math.hypot(event.clientX - start.x, event.clientY - start.y) > DRAG_THRESHOLD_PX
      ) {
        return true
      }

      const currentTarget = event.currentTarget
      return hasSelectedTextWithin(currentTarget instanceof Element ? currentTarget : null)
    },
  }
}
