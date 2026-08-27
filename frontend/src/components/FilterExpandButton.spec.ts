import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, ref } from 'vue'
import { describe, expect, it } from 'vitest'
import FilterExpandButton from './FilterExpandButton.vue'

// 用父组件监听器捕获 update:expanded 事件，规避部分环境下 VTU emitted() 记录不稳定的问题
function mountWithHost() {
  const expanded = ref(false)
  const received: boolean[] = []
  const Host = defineComponent({
    name: 'FilterExpandButtonHost',
    components: { FilterExpandButton },
    setup() {
      return {
        expanded,
        onToggle: (value: boolean) => {
          received.push(value)
        },
      }
    },
    template: '<FilterExpandButton :expanded="expanded" @update:expanded="onToggle" />',
  })
  const wrapper = mount(Host)
  return { wrapper, expanded, received }
}

describe('FilterExpandButton', () => {
  it('shows "更多筛选" and aria-expanded=false when collapsed', () => {
    const { wrapper } = mountWithHost()

    expect(wrapper.find('button').attributes('aria-expanded')).toBe('false')
    expect(wrapper.text()).toContain('更多筛选')
  })

  it('shows "收起筛选" and aria-expanded=true when expanded', async () => {
    const { wrapper, expanded } = mountWithHost()

    expanded.value = true
    await nextTick()

    expect(wrapper.find('button').attributes('aria-expanded')).toBe('true')
    expect(wrapper.text()).toContain('收起筛选')
  })

  it('emits the toggled value on click', async () => {
    const { wrapper, received } = mountWithHost()

    await wrapper.find('button').trigger('click')

    expect(received).toEqual([true])
  })

  it('rotates the chevron when expanded', async () => {
    const { wrapper, expanded } = mountWithHost()

    expanded.value = true
    await nextTick()

    expect(wrapper.find('.filter-collapse-chevron').classes()).toContain('is-expanded')
  })
})
