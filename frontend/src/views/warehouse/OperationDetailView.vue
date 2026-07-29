<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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
const sourceTypeLabels: Record<SourceType, string> = {
  MANUAL: '管理端手工录入',
  MINI_PROGRAM: '微信小程序出库',
  REVERSAL: '系统反向冲销',
  INITIALIZATION: '库存初始化',
}
const sourceTypeOptions = Object.entries(sourceTypeLabels).map(([value, label]) => ({
  label,
  value: value as SourceType,
}))
const editableSourceTypeOptions = computed(() => {
  const currentSource = operation.value?.source_type
  if (currentSource === 'MINI_PROGRAM' || currentSource === 'REVERSAL') {
    return sourceTypeOptions.filter((option) => option.value === currentSource)
  }
  return sourceTypeOptions.filter(
    (option) => option.value === 'MANUAL' || option.value === 'INITIALIZATION',
  )
})
const edit = reactive({
  operation_type: 'INBOUND' as OperationType,
  occurred_at: Date.now(),
  business_reason: '',
  receiver_unit: '',
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
    receiver_unit: value.receiver_unit || '',
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
  if (edit.operation_type === 'OUTBOUND' && !edit.business_reason.trim()) return '用途必填'
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
      receiver_unit:
        edit.operation_type === 'OUTBOUND' ? edit.receiver_unit.trim() || undefined : undefined,
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
    draggable: true,
    title: '确认修改流水',
    content: '修改流水将重新计算受影响物资的库存和后续流水快照。',
    positiveText: '确认修改',
    negativeText: '取消',
    onPositiveClick: save,
  })
}
function sourceTagType(sourceType: SourceType) {
  if (sourceType === 'MINI_PROGRAM') return 'info'
  if (sourceType === 'REVERSAL') return 'warning'
  if (sourceType === 'INITIALIZATION') return 'success'
  return 'default'
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
    <div class="detail-toolbar">
      <n-button secondary @click="router.back()">← 返回操作记录</n-button>
      <n-space v-if="auth.can('warehouse:write')">
        <n-button secondary @click="reverse">反向冲销</n-button>
        <n-button type="primary" @click="editing ? cancelEdit() : (editing = true)">{{
          editing ? '取消编辑' : '编辑流水'
        }}</n-button>
      </n-space>
    </div>

    <n-card :bordered="false" class="operation-hero">
      <div class="operation-hero-layout">
        <div class="operation-hero-main">
          <div class="operation-eyebrow">库存操作流水</div>
          <div class="operation-title-row">
            <h1>{{ operation.operation_no }}</h1>
            <n-tag
              round
              size="large"
              :type="operation.operation_type === 'INBOUND' ? 'success' : 'warning'"
            >
              {{ operation.operation_type === 'INBOUND' ? '入库' : '出库' }}
            </n-tag>
          </div>
          <div class="operation-meta-row">
            <span>发生时间</span>
            <strong>{{ formatShanghaiTime(operation.occurred_at) }}</strong>
            <span class="operation-meta-divider"></span>
            <span>操作来源</span>
            <n-tag :type="sourceTagType(operation.source_type)" size="small">
              {{ sourceTypeLabels[operation.source_type] }}
            </n-tag>
            <template v-if="operation.mini_program_user_name">
              <span class="operation-meta-divider"></span>
              <span>操作人</span>
              <strong>{{ operation.mini_program_user_name }}</strong>
            </template>
          </div>
        </div>
        <div class="operation-line-count">
          <span>物资明细</span>
          <div>
            <strong>{{ operation.lines.length }}</strong
            ><small>项</small>
          </div>
        </div>
      </div>
    </n-card>

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
              :disabled="['MINI_PROGRAM', 'REVERSAL'].includes(operation.source_type)"
          /></n-form-item>
          <n-form-item label="发生时间"
            ><n-date-picker v-model:value="edit.occurred_at" type="datetime" class="full-width"
          /></n-form-item>
          <n-form-item label="操作来源"
            ><n-select
              v-model:value="edit.source_type"
              :options="editableSourceTypeOptions"
              :disabled="['MINI_PROGRAM', 'REVERSAL'].includes(operation.source_type)"
          /></n-form-item>
          <n-form-item v-if="edit.operation_type === 'OUTBOUND'" label="领用单位"
            ><n-input v-model:value="edit.receiver_unit" maxlength="128"
          /></n-form-item>
          <n-form-item v-if="edit.operation_type === 'OUTBOUND'" label="领用人" required
            ><n-input v-model:value="edit.receiver_name" maxlength="64"
          /></n-form-item>
          <n-form-item v-if="edit.operation_type === 'OUTBOUND'" label="子项号"
            ><n-input v-model:value="edit.subitem_no" maxlength="64"
          /></n-form-item>
        </div>
        <n-form-item label="用途" :required="edit.operation_type === 'OUTBOUND'"
          ><n-input v-model:value="edit.business_reason" maxlength="500"
        /></n-form-item>
      </n-form>
      <n-descriptions v-else :column="3">
        <n-descriptions-item label="类型">{{
          operation.operation_type === 'INBOUND' ? '入库' : '出库'
        }}</n-descriptions-item>
        <n-descriptions-item label="操作来源">
          {{ sourceTypeLabels[operation.source_type] }}
        </n-descriptions-item>
        <n-descriptions-item label="发生时间">
          {{ formatShanghaiTime(operation.occurred_at) }}
        </n-descriptions-item>
        <n-descriptions-item label="用途" :span="2">{{
          operation.business_reason || '—'
        }}</n-descriptions-item>
        <n-descriptions-item v-if="operation.operation_type === 'OUTBOUND'" label="领用单位">{{
          operation.receiver_unit || '—'
        }}</n-descriptions-item>
        <n-descriptions-item v-if="operation.operation_type === 'OUTBOUND'" label="领用人">{{
          operation.receiver_name || '—'
        }}</n-descriptions-item>
        <n-descriptions-item v-if="operation.operation_type === 'OUTBOUND'" label="子项号">{{
          operation.subitem_no || '—'
        }}</n-descriptions-item>
        <n-descriptions-item label="请求幂等 ID" :span="2">{{
          operation.client_request_id
        }}</n-descriptions-item>
      </n-descriptions>
    </n-card>
    <n-card title="物资明细">
      <OperationLinesEditor v-if="editing" v-model:lines="edit.lines" :type="edit.operation_type" />
      <div v-else class="table-scroll" style="--table-min-width: 900px">
        <n-table :bordered="false">
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
      </div>
    </n-card>
    <n-space v-if="editing" justify="end"
      ><n-button @click="cancelEdit">取消</n-button
      ><n-button type="primary" :loading="saving" @click="confirmSave">保存修改</n-button></n-space
    >
  </div>
</template>

<style scoped>
.operation-hero {
  border: 1px solid #dce5ff;
  background: linear-gradient(135deg, #ffffff 0%, #f5f8ff 100%);
  box-shadow: 0 14px 34px rgba(43, 67, 133, 0.08);
}

.operation-hero-layout {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
}

.operation-hero-main {
  min-width: 0;
}

.operation-eyebrow {
  color: #5670c9;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.operation-title-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 8px;
}

.operation-title-row h1 {
  margin: 0;
  color: #172033;
  font-size: clamp(24px, 3vw, 34px);
  line-height: 1.25;
}

.operation-meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  color: #707b8f;
  font-size: 13px;
}

.operation-meta-row strong {
  color: #364153;
  font-weight: 600;
}

.operation-meta-divider {
  width: 1px;
  height: 14px;
  margin: 0 4px;
  background: #d9dfeb;
}

.operation-line-count {
  flex: none;
  min-width: 132px;
  padding: 18px 24px;
  border: 1px solid #dce5ff;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  text-align: center;
}

.operation-line-count > span {
  color: #748096;
  font-size: 13px;
}

.operation-line-count div {
  margin-top: 4px;
  color: #3658c7;
}

.operation-line-count strong {
  font-size: 30px;
  line-height: 1;
}

.operation-line-count small {
  margin-left: 4px;
  font-size: 13px;
}

@media (max-width: 720px) {
  .operation-hero-layout {
    align-items: stretch;
    flex-direction: column;
  }

  .operation-line-count {
    min-width: 0;
    text-align: left;
  }
}
</style>
