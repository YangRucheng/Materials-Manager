import { computed, ref, watch } from 'vue'

export function useImplicitAiSearch(source: () => string) {
  const expandedName = ref<string | null>(null)
  const searchName = computed(() => (expandedName.value ?? source()).trim() || undefined)

  watch(
    source,
    () => {
      expandedName.value = null
    },
    { flush: 'sync' },
  )

  function applyExpandedName(value: string) {
    expandedName.value = value.trim() || null
  }

  function clearExpandedName() {
    expandedName.value = null
  }

  return { searchName, applyExpandedName, clearExpandedName }
}
