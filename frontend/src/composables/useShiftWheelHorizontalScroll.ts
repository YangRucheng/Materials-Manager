import { onBeforeUnmount, onMounted, type Ref } from 'vue'

function findHorizontalScroller(root: HTMLElement, target: EventTarget | null): HTMLElement | null {
  const element = target instanceof Element ? target : null
  const localScroller = element?.closest<HTMLElement>(
    '.n-data-table-base-table-body .n-scrollbar-container',
  )
  if (localScroller && root.contains(localScroller)) return localScroller
  return root.querySelector<HTMLElement>('.n-data-table-base-table-body .n-scrollbar-container')
}

export function useShiftWheelHorizontalScroll(rootRef: Ref<HTMLElement | null>): void {
  function handleWheel(event: WheelEvent) {
    if (!event.shiftKey || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return
    const root = rootRef.value
    if (!root) return
    const scroller = findHorizontalScroller(root, event.target)
    if (!scroller || scroller.scrollWidth <= scroller.clientWidth) return

    const previous = scroller.scrollLeft
    scroller.scrollLeft += event.deltaY
    if (scroller.scrollLeft !== previous) event.preventDefault()
  }

  onMounted(() => rootRef.value?.addEventListener('wheel', handleWheel, { passive: false }))
  onBeforeUnmount(() => rootRef.value?.removeEventListener('wheel', handleWheel))
}
