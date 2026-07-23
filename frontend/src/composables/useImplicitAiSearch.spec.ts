import { ref } from 'vue'
import { describe, expect, it } from 'vitest'
import { useImplicitAiSearch } from './useImplicitAiSearch'

describe('useImplicitAiSearch', () => {
  it('uses expanded terms without changing the visible input', () => {
    const input = ref('电机')
    const { searchName, applyExpandedName, clearExpandedName } = useImplicitAiSearch(
      () => input.value,
    )

    applyExpandedName('电机|电动机')
    expect(input.value).toBe('电机')
    expect(searchName.value).toBe('电机|电动机')

    input.value = '水泵'
    expect(searchName.value).toBe('水泵')

    applyExpandedName('水泵|泵')
    clearExpandedName()
    expect(searchName.value).toBe('水泵')
  })
})
