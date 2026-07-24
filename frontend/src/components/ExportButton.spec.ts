import { mount } from '@vue/test-utils'
import { NDropdown } from 'naive-ui'
import { describe, expect, it } from 'vitest'
import ExportButton from './ExportButton.vue'

describe('ExportButton', () => {
  it('directly emits the only export option', async () => {
    const wrapper = mount(ExportButton, {
      props: {
        options: [{ label: '导出查询结果', key: 'results' }],
      },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('select')).toEqual([['results']])
  })

  it('renders multiple export options in a dropdown', async () => {
    const wrapper = mount(ExportButton, {
      props: {
        options: [
          { label: '导出查询结果', key: 'results' },
          { label: '导出采购申请表', key: 'purchase-application' },
        ],
      },
    })

    wrapper.findComponent(NDropdown).vm.$emit('select', 'purchase-application')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('select')).toEqual([['purchase-application']])
  })

  it('does not emit a disabled direct option', async () => {
    const wrapper = mount(ExportButton, {
      props: {
        options: [{ label: '导出查询结果', key: 'results', disabled: true }],
      },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('select')).toBeUndefined()
  })
})
