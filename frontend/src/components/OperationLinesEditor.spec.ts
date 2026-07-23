import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import OperationLinesEditor from './OperationLinesEditor.vue'
import type { StockMaterial } from '@/api/generated'

const material: StockMaterial = {
  id: 7,
  name: '微型断路器',
  model_spec: 'C20 3P',
  unit_id: 1,
  unit_name: '个',
  current_qty: '10',
  images: [],
  created_at: '2026-07-18T00:00:00Z',
  updated_at: '2026-07-18T00:00:00Z',
  version: 1,
}

const MaterialSelectorStub = defineComponent({
  name: 'MaterialSelector',
  emits: ['update:value', 'select'],
  setup(_, { emit }) {
    function choose() {
      emit('update:value', material.id)
      emit('select', material)
    }
    return { choose }
  },
  template: '<button class="choose-material" @click="choose">选择物资</button>',
})

describe('OperationLinesEditor', () => {
  it('keeps the selected material when the selector emits its consecutive events', async () => {
    const wrapper = mount(OperationLinesEditor, {
      props: {
        lines: [{ stock_material_id: null, quantity: '' }],
        type: 'INBOUND',
      },
      global: {
        stubs: {
          MaterialSelector: MaterialSelectorStub,
          QuantityInput: true,
          NInputNumber: true,
          NButton: true,
        },
      },
    })

    await wrapper.get('.choose-material').trigger('click')

    const updates = wrapper.emitted('update:lines')
    expect(updates).toHaveLength(1)
    expect(updates?.[0]?.[0]).toEqual([{ stock_material_id: material.id, quantity: '', material }])
  })
})
