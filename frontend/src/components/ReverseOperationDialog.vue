<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import type { StockOperation } from '@/api/generated'
import { inventoryApi } from '@/api/inventory'
import QuantityInput from '@/components/QuantityInput.vue'
import { compareDecimal, isDecimalString } from '@/utils/decimal'

const props = defineProps<{ show: boolean; operation: StockOperation | null }>()
const emit = defineEmits<{ 'update:show': [value: boolean]; reversed: [id: number] }>()

const message = useMessage()
const submitting = ref(false)
const requestId = ref<string | null>(null)
const lines = reactive<Array<{ stock_material_id: number; quantity: string; max: string }>>([])

// 用 computed + update:show 实现 v-model，避免直接改写 prop
const showModel = computed({
  get: () => props.show,
  set: (value: boolean) => emit('update:show', value),
})

watch(
  () => [props.show, props.operation],
  () => {
    if (!props.show || !props.operation) return
    // 幂等 id 在弹窗打开时生成一次，确认重试复用，成功或彻底失败后作废
    requestId.value = crypto.randomUUID()
    lines.splice(
      0,
      lines.length,
      ...props.operation.lines.map((line) => ({
        stock_material_id: line.stock_material_id,
        quantity: line.remaining_qty,
        max: line.remaining_qty,
      })),
    )
  },
)

const allValid = computed(() =>
  lines.every(
    (line) =>
      isDecimalString(line.quantity, 1) &&
      compareDecimal(line.quantity, '0') > 0 &&
      compareDecimal(line.quantity, line.max) <= 0,
  ),
)

async function confirm() {
  if (!props.operation || !allValid.value) {
    message.error('请为每项物资填写有效且不超过剩余可冲数量的冲销数量')
    return
  }
  submitting.value = true
  try {
    const result = await inventoryApi.reverseOperation(props.operation.id, {
      client_request_id: requestId.value || crypto.randomUUID(),
      reason: `冲销 ${props.operation.operation_no}`,
      lines: lines.map((line) => ({
        stock_material_id: line.stock_material_id,
        quantity: line.quantity,
      })),
    })
    message.success(`已生成冲销流水 ${result.operation_no}`)
    requestId.value = null
    emit('update:show', false)
    emit('reversed', result.id)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '冲销失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <n-modal
    v-model:show="showModel"
    preset="card"
    draggable
    title="反向冲销"
    style="width: 640px"
    :mask-closable="false"
  >
    <n-alert type="warning" style="margin-bottom: 16px">
      反向冲销将生成一条与原流水相反方向的流水（原入库 → 出库，原出库 →
      入库）。可为每项物资指定冲销数量， 未冲销的剩余数量可后续再次冲销。
    </n-alert>
    <n-table v-if="operation" :bordered="false" size="small">
      <thead>
        <tr>
          <th>物资</th>
          <th>型号规格</th>
          <th>原数量</th>
          <th>剩余可冲</th>
          <th>本次冲销</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(line, index) in lines" :key="line.stock_material_id">
          <td>{{ operation.lines[index].material_name }}</td>
          <td>{{ operation.lines[index].model_spec }}</td>
          <td>{{ operation.lines[index].quantity }} {{ operation.lines[index].unit_name }}</td>
          <td>{{ line.max }} {{ operation.lines[index].unit_name }}</td>
          <td style="width: 160px">
            <QuantityInput
              v-model:value="line.quantity"
              :decimal-places="1"
              :max="line.max"
              placeholder="冲销数量"
              ><template #suffix>{{ operation.lines[index].unit_name }}</template></QuantityInput
            >
          </td>
        </tr>
      </tbody>
    </n-table>
    <template #footer>
      <n-space justify="end">
        <n-button :disabled="submitting" @click="emit('update:show', false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="confirm">确认冲销</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
