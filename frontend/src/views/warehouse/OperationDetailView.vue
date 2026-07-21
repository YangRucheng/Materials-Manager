<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useDialog, useMessage } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import type { OperationType, SourceType, StockOperation } from '@/api/generated'
import { inventoryApi } from '@/api/inventory'
import { useAuthStore } from '@/stores/auth'
import { formatShanghaiTime, toIsoWithTimezone } from '@/utils/time'
import OperationLinesEditor, {
  type OperationLineModel,
} from '@/components/OperationLinesEditor.vue'
import { isDecimalString } from '@/utils/decimal'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const dialog = useDialog()
const operation = ref<StockOperation | null>(null)
const loading = ref(true)
const editing = ref(false)
const saving = ref(false)
const edit = reactive({
  operation_type: 'INBOUND' as OperationType,
  occurred_at: Date.now(),
  business_reason: '',
  receiver_name: '',
  subitem_no: '',
  source_type: 'MANUAL' as SourceType,
  lines: [] as OperationLineModel[],
})

async function resetEditor(value: StockOperation) {
  const materials = await Promise.all(
    value.lines.map((line) => inventoryApi.material(line.stock_material_id)),
  )
  Object.assign(edit, {
    operation_type: value.operation_type,
    occurred_at: new Date(value.occurred_at).getTime(),
    business_reason: value.business_reason,
    receiver_name: value.receiver_name || '',
    subitem_no: value.subitem_no || '',
    source_type: value.source_type,
    lines: value.lines.map((line, index) => ({
      stock_material_id: line.stock_material_id,
      quantity: line.quantity,
      material: materials[index],
    })),
  })
}
async function load() {
  loading.value = true
  try {
    operation.value = await inventoryApi.operation(Number(route.params.id))
    await resetEditor(operation.value)
  } finally {
    loading.value = false
  }
}
function validationError(): string | null {
  if (edit.operation_type === 'OUTBOUND' && !edit.business_reason.trim()) return '业务原因必填'
  if (edit.operation_type === 'OUTBOUND' && !edit.receiver_name.trim()) return '领用人必填'
  if (
    !edit.lines.length ||
    edit.lines.some((line) => !line.stock_material_id || !isDecimalString(line.quantity, 1))
  )
    return '请完整填写物资和有效数量'
  return null
}
async function save() {
  if (!operation.value) return
  saving.value = true
  try {
    operation.value = await inventoryApi.updateOperation(operation.value.id, {
      version: operation.value.version,
      operation_type: edit.operation_type,
      occurred_at: toIsoWithTimezone(edit.occurred_at),
      business_reason: edit.business_reason.trim(),
      receiver_name:
        edit.operation_type === 'OUTBOUND' ? edit.receiver_name.trim() || undefined : undefined,
      subitem_no:
        edit.operation_type === 'OUTBOUND' ? edit.subitem_no.trim() || undefined : undefined,
      source_type: edit.source_type,
      lines: edit.lines.map((line) => ({
        stock_material_id: line.stock_material_id!,
        quantity: line.quantity,
      })),
    })
    message.success('流水已修改，库存已重新计算')
    editing.value = false
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}
function confirmSave() {
  const error = validationError()
  if (error) {
    message.error(error)
    return
  }
  dialog.warning({
    title: '确认修改流水',
    content: '修改流水将重新计算受影响物资的库存和后续流水快照。',
    positiveText: '确认修改',
    negativeText: '取消',
    onPositiveClick: save,
  })
}
async function cancelEdit() {
  if (operation.value) await resetEditor(operation.value)
  editing.value = false
}
async function reverse() {
  if (!operation.value) return
  try {
    const result = await inventoryApi.reverseOperation(operation.value.id, {
      client_request_id: crypto.randomUUID(),
      reason: `冲销 ${operation.value.operation_no}`,
    })
    message.success(`已生成冲销流水 ${result.operation_no}`)
    await router.push(`/warehouse/operations/${result.id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '冲销失败')
  }
}
onMounted(load)
</script>

<template>
  <div v-if="operation" v-loading="loading" class="page">
    <div class="page-header">
      <div>
        <n-button text @click="router.back()">← 返回操作记录</n-button>
        <h1 class="page-title">{{ operation.operation_no }}</h1>
        <p class="page-subtitle">
          {{ operation.operation_type === 'INBOUND' ? '入库' : '出库' }} ·
          {{ formatShanghaiTime(operation.occurred_at) }}
        </p>
      </div>
      <n-space v-if="auth.can('warehouse:write')">
        <n-button @click="reverse">反向冲销</n-button>
        <n-button type="primary" @click="editing ? cancelEdit() : (editing = true)">{{
          editing ? '取消编辑' : '编辑流水'
        }}</n-button>
      </n-space>
    </div>
    <n-alert v-if="editing" type="warning" title="修改影响提示"
      >保存后，后端会按发生时间重放相关物资的全部流水；允许形成负库存。</n-alert
    >
    <n-card title="单据信息">
      <n-form v-if="editing" label-placement="top">
        <div class="form-grid">
          <n-form-item label="业务类型"
            ><n-select
              v-model:value="edit.operation_type"
              :options="[
                { label: '入库', value: 'INBOUND' },
                { label: '出库', value: 'OUTBOUND' },
              ]"
          /></n-form-item>
          <n-form-item label="发生时间"
            ><n-date-picker v-model:value="edit.occurred_at" type="datetime" class="full-width"
          /></n-form-item>
          <n-form-item label="来源类型"
            ><n-select
              v-model:value="edit.source_type"
              :options="
                ['MANUAL', 'REVERSAL', 'INITIALIZATION'].map((value) => ({
                  label: value,
                  value,
                }))
              "
          /></n-form-item>
          <n-form-item v-if="edit.operation_type === 'OUTBOUND'" label="领用人" required
            ><n-input v-model:value="edit.receiver_name" maxlength="64"
          /></n-form-item>
          <n-form-item v-if="edit.operation_type === 'OUTBOUND'" label="子项号"
            ><n-input v-model:value="edit.subitem_no" maxlength="64" placeholder="选填"
          /></n-form-item>
        </div>
        <n-form-item label="业务原因" required
          ><n-input v-model:value="edit.business_reason" maxlength="500"
        /></n-form-item>
      </n-form>
      <n-descriptions v-else :column="3">
        <n-descriptions-item label="类型">{{
          operation.operation_type === 'INBOUND' ? '入库' : '出库'
        }}</n-descriptions-item>
        <n-descriptions-item label="来源">{{ operation.source_type }}</n-descriptions-item>
        <n-descriptions-item label="业务原因" :span="2">{{
          operation.business_reason || '—'
        }}</n-descriptions-item>
        <n-descriptions-item label="领用人">{{
          operation.receiver_name || '—'
        }}</n-descriptions-item>
        <n-descriptions-item label="子项号">{{ operation.subitem_no || '—' }}</n-descriptions-item>
        <n-descriptions-item label="请求幂等 ID" :span="2">{{
          operation.client_request_id
        }}</n-descriptions-item>
      </n-descriptions>
    </n-card>
    <n-card title="物资明细">
      <OperationLinesEditor v-if="editing" v-model:lines="edit.lines" :type="edit.operation_type" />
      <n-table v-else :bordered="false">
        <thead>
          <tr>
            <th>物资</th>
            <th>型号规格</th>
            <th>数量</th>
            <th>操作前</th>
            <th>操作后</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(line, index) in operation.lines" :key="line.id || index">
            <td>{{ line.material_name }}</td>
            <td>{{ line.model_spec }}</td>
            <td>{{ line.quantity }} {{ line.unit_name }}</td>
            <td>{{ line.before_qty }}</td>
            <td>{{ line.after_qty }}</td>
          </tr>
        </tbody>
      </n-table>
    </n-card>
    <n-space v-if="editing" justify="end"
      ><n-button @click="cancelEdit">取消</n-button
      ><n-button type="primary" :loading="saving" @click="confirmSave">保存修改</n-button></n-space
    >
  </div>
</template>
