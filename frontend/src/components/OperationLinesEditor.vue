<script setup lang="ts">
import { computed, onMounted } from 'vue'
import MaterialSelector from './MaterialSelector.vue'
import QuantityInput from './QuantityInput.vue'
import type { StockMaterial } from '@/api/generated'
import { compareDecimal, subtractDecimal } from '@/utils/decimal'
import { useDictionaryStore } from '@/stores/dictionaries'

export interface OperationLineModel {
  stock_material_id: number | null
  quantity: string
  purchase_request_line_id?: number
  material?: StockMaterial
}

const props = withDefaults(
  defineProps<{
    lines: OperationLineModel[]
    type: 'INBOUND' | 'OUTBOUND'
    disabled?: boolean
    showPurchaseLink?: boolean
  }>(),
  { disabled: false, showPurchaseLink: false },
)
const emit = defineEmits<{ 'update:lines': [lines: OperationLineModel[]] }>()
const dictionaries = useDictionaryStore()
const selectedIds = computed(() =>
  props.lines.map((x) => x.stock_material_id).filter((x): x is number => x !== null),
)
const gridColumns = computed(() =>
  [
    'minmax(300px, 2fr)',
    '120px',
    '180px',
    ...(props.type === 'OUTBOUND' ? ['100px'] : []),
    ...(props.showPurchaseLink ? ['160px'] : []),
    '60px',
  ].join(' '),
)
function patch(index: number, value: Partial<OperationLineModel>) {
  const next = props.lines.map((line, i) => (i === index ? { ...line, ...value } : line))
  emit('update:lines', next)
}
function add() {
  emit('update:lines', [...props.lines, { stock_material_id: null, quantity: '' }])
}
function remove(index: number) {
  emit(
    'update:lines',
    props.lines.filter((_, i) => i !== index),
  )
}
function decimalPlaces(line: OperationLineModel): number {
  return dictionaries.getUnit(line.material?.unit_id)?.decimal_places ?? 3
}
onMounted(() => void dictionaries.load())
</script>

<template>
  <div class="line-table">
    <div class="line-head" :style="{ gridTemplateColumns: gridColumns }">
      <span>物资</span><span>当前库存</span><span>数量</span
      ><span v-if="type === 'OUTBOUND'">出库后</span
      ><span v-if="showPurchaseLink">关联请购行 ID</span><span>操作</span>
    </div>
    <div
      v-for="(line, index) in lines"
      :key="index"
      class="line-row"
      :style="{ gridTemplateColumns: gridColumns }"
    >
      <MaterialSelector
        :value="line.stock_material_id"
        :disabled="disabled"
        :exclude-ids="selectedIds.filter((id) => id !== line.stock_material_id)"
        @update:value="patch(index, { stock_material_id: $event })"
        @select="patch(index, { material: $event })"
      />
      <span>{{ line.material?.current_qty ?? '—' }} {{ line.material?.unit_name }}</span>
      <QuantityInput
        :value="line.quantity"
        :disabled="disabled"
        :decimal-places="decimalPlaces(line)"
        @update:value="patch(index, { quantity: $event })"
        ><template #suffix>{{ line.material?.unit_name }}</template></QuantityInput
      >
      <span
        v-if="type === 'OUTBOUND'"
        :class="{
          'danger-text':
            line.material &&
            line.quantity &&
            compareDecimal(line.quantity, line.material.current_qty) > 0,
        }"
        >{{
          line.material && line.quantity
            ? subtractDecimal(line.material.current_qty, line.quantity)
            : '—'
        }}</span
      >
      <n-input-number
        v-if="showPurchaseLink"
        :value="line.purchase_request_line_id"
        :show-button="false"
        placeholder="可选"
        @update:value="patch(index, { purchase_request_line_id: $event ?? undefined })"
      />
      <n-button
        v-if="!disabled"
        text
        type="error"
        :disabled="lines.length === 1"
        @click="remove(index)"
        >删除</n-button
      >
    </div>
    <n-button v-if="!disabled" dashed block @click="add">+ 添加物资</n-button>
  </div>
</template>

<style scoped>
.line-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.line-head,
.line-row {
  display: grid;
  grid-template-columns: minmax(300px, 2fr) 120px 180px 60px;
  gap: 12px;
  align-items: center;
}
.line-head {
  color: #6b7280;
  font-size: 13px;
  padding: 0 4px;
}
.line-row {
  min-height: 44px;
}
</style>
