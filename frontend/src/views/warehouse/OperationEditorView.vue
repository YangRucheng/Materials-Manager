<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import OperationLinesEditor, {
  type OperationLineModel,
} from '@/components/OperationLinesEditor.vue'
import { inventoryApi } from '@/api/inventory'
import { isDecimalString } from '@/utils/decimal'
import { toIsoWithTimezone } from '@/utils/time'

const props = defineProps<{ operationType: 'INBOUND' | 'OUTBOUND' }>()
const route = useRoute()
const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const submitting = ref(false)
const occurredAt = ref(Date.now())
const requestId = ref<string | null>(null)
const model = reactive({
  business_reason: '',
  receiver_name: '',
  subitem_no: '',
  source_type: 'MANUAL' as 'MANUAL' | 'INITIALIZATION',
  lines: [{ stock_material_id: null, quantity: '' }] as OperationLineModel[],
})
const title = computed(() => (props.operationType === 'INBOUND' ? '办理入库' : '办理出库'))
function validate(): string | null {
  if (props.operationType === 'OUTBOUND' && !model.business_reason.trim()) return '请填写业务原因'
  if (props.operationType === 'OUTBOUND' && !model.receiver_name.trim()) return '请填写领用人'
  if (
    !model.lines.length ||
    model.lines.some((x) => !x.stock_material_id || !isDecimalString(x.quantity, 1))
  )
    return '请完整填写物资和有效数量'
  return null
}
async function submit() {
  requestId.value ||= crypto.randomUUID()
  try {
    const payload = {
      client_request_id: requestId.value,
      occurred_at: toIsoWithTimezone(occurredAt.value),
      source_type: model.source_type,
      business_reason: model.business_reason.trim(),
      receiver_name: model.receiver_name.trim() || undefined,
      subitem_no: model.subitem_no.trim() || undefined,
      lines: model.lines.map((x) => ({
        stock_material_id: x.stock_material_id!,
        quantity: x.quantity,
      })),
    }
    const result =
      props.operationType === 'INBOUND'
        ? await inventoryApi.inbound(payload)
        : await inventoryApi.outbound(payload)
    message.success(`${title.value}成功：${result.operation_no}`)
    await router.replace(`/warehouse/operations/${result.id}`)
  } catch (e) {
    requestId.value = null
    message.error(e instanceof Error ? e.message : '提交失败')
  } finally {
    submitting.value = false
  }
}
function confirmSubmit() {
  if (submitting.value) return
  const error = validate()
  if (error) {
    message.error(error)
    return
  }
  submitting.value = true
  dialog.warning({
    title: `确认${props.operationType === 'INBOUND' ? '入库' : '出库'}`,
    content: `将为 ${model.lines.length} 项物资生成库存流水，确认继续？`,
    positiveText: '确认提交',
    negativeText: '取消',
    maskClosable: false,
    closable: false,
    onPositiveClick: submit,
    onNegativeClick: () => {
      submitting.value = false
    },
  })
}
onMounted(async () => {
  const id = Number(route.query.material_id)
  if (id) {
    const material = await inventoryApi.material(id)
    model.lines = [
      {
        stock_material_id: id,
        quantity: String(route.query.quantity || ''),
        material,
      },
    ]
  }
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ title }}</h1>
      </div>
    </div>
    <n-card title="业务信息"
      ><n-form label-placement="top"
        ><div class="form-grid">
          <n-form-item label="发生时间" required
            ><n-date-picker
              v-model:value="occurredAt"
              type="datetime"
              clearable
              class="full-width" /></n-form-item
          ><n-form-item v-if="operationType === 'INBOUND'" label="来源类型"
            ><n-select
              v-model:value="model.source_type"
              :options="[
                { label: '手工入库', value: 'MANUAL' },
                { label: '初始化入库', value: 'INITIALIZATION' },
              ]" /></n-form-item
          ><n-form-item v-if="operationType === 'OUTBOUND'" label="领用人" required
            ><n-input v-model:value="model.receiver_name" maxlength="64" /></n-form-item
          ><n-form-item v-if="operationType === 'OUTBOUND'" label="子项号"
            ><n-input v-model:value="model.subitem_no" maxlength="64" placeholder="选填"
          /></n-form-item>
        </div>
        <n-form-item label="业务原因" :required="operationType === 'OUTBOUND'"
          ><n-input
            v-model:value="model.business_reason"
            maxlength="500"
            show-count
            :placeholder="
              operationType === 'INBOUND' ? '可选' : '说明本次库存变化原因'
            " /></n-form-item></n-form
    ></n-card>
    <n-card title="物资明细"
      ><OperationLinesEditor v-model:lines="model.lines" :type="operationType"
    /></n-card>
    <n-space justify="end"
      ><n-button @click="router.back()">取消</n-button
      ><n-button type="primary" :loading="submitting" :disabled="submitting" @click="confirmSubmit"
        >确认{{ operationType === 'INBOUND' ? '入库' : '出库' }}</n-button
      ></n-space
    >
  </div>
</template>
