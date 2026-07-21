import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import ColumnVisibilityPicker from './ColumnVisibilityPicker.vue'

const options = [
  { label: '计划 ID', value: 'plan_no' },
  { label: '名称', value: 'name' },
  { label: '型号规格', value: 'model_spec' },
]

describe('ColumnVisibilityPicker', () => {
  beforeEach(() => localStorage.clear())

  it('restores valid visible columns and ignores removed columns', () => {
    localStorage.setItem('columns', JSON.stringify(['name', 'removed']))

    const wrapper = mount(ColumnVisibilityPicker, {
      props: { value: options.map((option) => option.value), options, storageKey: 'columns' },
    })

    expect(wrapper.emitted('update:value')).toEqual([[['name']]])
  })

  it('persists later column selections', async () => {
    const wrapper = mount(ColumnVisibilityPicker, {
      props: { value: options.map((option) => option.value), options, storageKey: 'columns' },
    })

    await wrapper.setProps({ value: ['plan_no', 'model_spec'] })

    expect(JSON.parse(localStorage.getItem('columns') || 'null')).toEqual([
      'plan_no',
      'model_spec',
    ])
  })

  it('keeps page defaults when stored data is invalid', () => {
    localStorage.setItem('columns', '{invalid')

    const wrapper = mount(ColumnVisibilityPicker, {
      props: { value: options.map((option) => option.value), options, storageKey: 'columns' },
    })

    expect(wrapper.emitted('update:value')).toBeUndefined()
  })
})
