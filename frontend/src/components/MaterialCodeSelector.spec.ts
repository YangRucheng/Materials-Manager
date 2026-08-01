import { flushPromises, mount } from '@vue/test-utils'
import { NButton, NConfigProvider, NInput, NMessageProvider, NModal, NTag } from 'naive-ui'
import { h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MaterialCodeSelector from './MaterialCodeSelector.vue'

const { materialCodes } = vi.hoisted(() => ({
  materialCodes: vi.fn(),
}))

vi.mock('@/api/procurement', () => ({
  procurementApi: { materialCodes },
}))

function mountSelector() {
  return mount(NConfigProvider, {
    slots: {
      default: () =>
        h(NMessageProvider, null, {
          default: () =>
            h(MaterialCodeSelector, {
              modelValue: 'DQ-001',
              defaultName: '接触器',
              defaultModelSpec: 'CJX2-2510',
            }),
        }),
    },
    global: {
      components: { NInput, NModal, NTag },
      stubs: { NDataTable: true, NPagination: true },
    },
  })
}

function button(wrapper: ReturnType<typeof mountSelector>, label: string) {
  const selector = wrapper.findComponent(MaterialCodeSelector)
  const target = selector.findAllComponents(NButton).find((item) => item.text().trim() === label)
  if (!target) throw new Error(`button not found: ${label}`)
  return target
}

describe('MaterialCodeSelector', () => {
  beforeEach(() => {
    materialCodes.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 })
  })

  it('uses plan values as defaults and supports reset and clear', async () => {
    const wrapper = mountSelector()

    await button(wrapper, '选择编码').trigger('click')
    await flushPromises()
    expect(materialCodes).toHaveBeenLastCalledWith({
      material_code: 'DQ-001',
      name: '接触器',
      model_spec: 'CJX2-2510',
      page: 1,
      page_size: 10,
    })

    const inputs = wrapper.findComponent(MaterialCodeSelector).findAllComponents(NInput)
    await inputs.find((item) => item.props('placeholder') === '输入物资名称')!.setValue('水泵')
    await inputs.find((item) => item.props('placeholder') === '输入型号规格')!.setValue('M60')
    await button(wrapper, '重置').trigger('click')
    await flushPromises()
    expect(materialCodes).toHaveBeenLastCalledWith({
      material_code: 'DQ-001',
      name: '接触器',
      model_spec: 'CJX2-2510',
      page: 1,
      page_size: 10,
    })

    await button(wrapper, '清空').trigger('click')
    await flushPromises()
    expect(materialCodes).toHaveBeenLastCalledWith({
      material_code: undefined,
      name: undefined,
      model_spec: undefined,
      page: 1,
      page_size: 10,
    })
  })
})
