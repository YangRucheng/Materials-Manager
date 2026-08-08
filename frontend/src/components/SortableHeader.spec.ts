import { mount } from '@vue/test-utils'
import { NDropdown } from 'naive-ui'
import { describe, expect, it } from 'vitest'
import SortableHeader from './SortableHeader.vue'

const baseProps = {
  label: '名称',
  sortByKey: 'name',
  sortBy: null,
  sortOrder: null as 'asc' | 'desc' | null,
}

describe('SortableHeader', () => {
  it('renders three sort options in a dropdown', () => {
    const wrapper = mount(SortableHeader, { props: baseProps })

    const dropdown = wrapper.findComponent(NDropdown)
    expect(dropdown.props('options')).toEqual([
      { label: '默认', key: 'default' },
      { label: '升序', key: 'asc' },
      { label: '降序', key: 'desc' },
    ])
    expect(wrapper.text()).toContain('名称')
  })

  it('is inactive with value "default" when this column is not sorted', () => {
    const wrapper = mount(SortableHeader, { props: baseProps })

    expect(wrapper.find('.sortable-header').classes()).not.toContain('sortable-header--active')
    expect(wrapper.find('.sortable-header__arrow').exists()).toBe(false)
    expect(wrapper.findComponent(NDropdown).props('value')).toBe('default')
  })

  it('is active showing an up arrow when this column sorts ascending', () => {
    const wrapper = mount(SortableHeader, {
      props: { ...baseProps, sortBy: 'name', sortOrder: 'asc' },
    })

    expect(wrapper.find('.sortable-header').classes()).toContain('sortable-header--active')
    expect(wrapper.find('.sortable-header__arrow').text()).toBe('↑')
    expect(wrapper.findComponent(NDropdown).props('value')).toBe('asc')
  })

  it('shows a down arrow when this column sorts descending', () => {
    const wrapper = mount(SortableHeader, {
      props: { ...baseProps, sortBy: 'name', sortOrder: 'desc' },
    })

    expect(wrapper.find('.sortable-header').classes()).toContain('sortable-header--active')
    expect(wrapper.find('.sortable-header__arrow').text()).toBe('↓')
    expect(wrapper.findComponent(NDropdown).props('value')).toBe('desc')
  })

  it('is inactive when another column is sorted', () => {
    const wrapper = mount(SortableHeader, {
      props: { ...baseProps, sortBy: 'plan_no', sortOrder: 'desc' },
    })

    expect(wrapper.find('.sortable-header').classes()).not.toContain('sortable-header--active')
    expect(wrapper.find('.sortable-header__arrow').exists()).toBe(false)
    expect(wrapper.findComponent(NDropdown).props('value')).toBe('default')
  })

  it('emits the chosen order on dropdown select', async () => {
    const wrapper = mount(SortableHeader, { props: baseProps })

    wrapper.findComponent(NDropdown).vm.$emit('select', 'asc')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('select')).toEqual([['asc']])
  })
})
