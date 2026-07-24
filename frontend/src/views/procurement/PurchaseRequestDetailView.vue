<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NInputGroup, useMessage } from 'naive-ui'
import type { FileObject, PurchaseRecord, PurchaseRecordWrite } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionaries'
import ImageUploader from '@/components/ImageUploader.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import { dateToTimestamp, formatShanghaiTime, toShanghaiDate } from '@/utils/time'
import { purchaseCategoryOptions } from '@/constants/purchase'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const dictionaries = useDictionaryStore()
const message = useMessage()
const record = ref<PurchaseRecord | null>(null)
const loading = ref(true)
const saving = ref(false)
const images = ref<FileObject[]>([])
const planDate = ref<number | null>(null)
const purchaseDate = ref<number | null>(null)
const consolidationDate = ref<number | null>(null)
const sailingDate = ref<number | null>(null)
const form = reactive<PurchaseRecordWrite>({
  plan_date: '',
  material_code: '',
  category: '',
  demand_department: '',
  material_name: '',
  model_spec: '',
  unit_id: null,
  actual_demand_person: '',
  purchase_responsible: '',
  purchase_qty: '',
  usage: '',
  subitem_no: '',
  plan_remark: '',
  stock_material_id: undefined,
  image_ids: [],
  purchase_order_no: '',
  trace_no: '',
  contract_no: '',
  vessel_no: '',
  consolidation_date: undefined,
  consolidation_port: '',
  sailing_date: undefined,
  purchase_date: '',
  salesperson: '',
  status: '',
  record_remark: '',
  version: 1,
})

function syncForm(value: PurchaseRecord) {
  Object.assign(form, {
    plan_date: value.plan_date,
    material_code: value.material_code || '',
    category: value.category || '',
    demand_department: value.demand_department,
    material_name: value.material_name,
    model_spec: value.model_spec,
    unit_id: value.unit_id,
    actual_demand_person: value.actual_demand_person,
    purchase_responsible: value.purchase_responsible,
    purchase_qty: value.purchase_qty,
    usage: value.usage,
    subitem_no: value.subitem_no || '',
    plan_remark: value.plan_remark || '',
    stock_material_id: value.stock_material_id,
    image_ids: value.images.map((image) => image.id),
    purchase_order_no: value.purchase_order_no || '',
    trace_no: value.trace_no || '',
    contract_no: value.contract_no || '',
    vessel_no: value.vessel_no || '',
    consolidation_date: value.consolidation_date,
    consolidation_port: value.consolidation_port || '',
    sailing_date: value.sailing_date,
    purchase_date: value.purchase_date || '',
    salesperson: value.salesperson || '',
    status: value.status,
    record_remark: value.record_remark || '',
    version: value.version,
  })
  planDate.value = dateToTimestamp(value.plan_date)
  purchaseDate.value = dateToTimestamp(value.purchase_date)
  consolidationDate.value = dateToTimestamp(value.consolidation_date)
  sailingDate.value = dateToTimestamp(value.sailing_date)
  images.value = [...value.images]
}

async function load() {
  loading.value = true
  try {
    record.value = await procurementApi.record(Number(route.params.id))
    syncForm(record.value)
  } finally {
    loading.value = false
  }
}

async function save() {
  if (
    !record.value ||
    !planDate.value ||
    !purchaseDate.value ||
    !form.material_name.trim() ||
    !form.model_spec.trim() ||
    !form.unit_id ||
    !form.actual_demand_person.trim() ||
    !form.purchase_responsible.trim() ||
    !form.purchase_qty ||
    !form.usage.trim() ||
    !form.status.trim()
  ) {
    message.error('请完整填写日期、物资、申购数量、用途、人员和状态')
    return
  }
  saving.value = true
  try {
    record.value = await procurementApi.updateRecord(record.value.line_id, {
      ...form,
      plan_date: toShanghaiDate(planDate.value),
      purchase_date: toShanghaiDate(purchaseDate.value),
      consolidation_date: consolidationDate.value
        ? toShanghaiDate(consolidationDate.value)
        : undefined,
      sailing_date: sailingDate.value ? toShanghaiDate(sailingDate.value) : undefined,
      material_code: form.material_code?.trim() || undefined,
      category: form.category?.trim() || undefined,
      subitem_no: form.subitem_no?.trim() || undefined,
      plan_remark: form.plan_remark?.trim() || undefined,
      record_remark: form.record_remark?.trim() || undefined,
      purchase_order_no: form.purchase_order_no?.trim() || null,
      trace_no: form.trace_no?.trim() || null,
      contract_no: form.contract_no?.trim() || null,
      vessel_no: form.vessel_no?.trim() || null,
      consolidation_port: form.consolidation_port?.trim() || null,
      salesperson: form.salesperson?.trim() || undefined,
      image_ids: images.value.map((image) => image.id),
    })
    syncForm(record.value)
    message.success('申购记录已保存')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void dictionaries.load()
  void load()
})
</script>

<template>
  <div v-if="record" v-loading="loading" class="page">
    <div class="detail-toolbar">
      <n-button secondary @click="router.push('/procurement/records')">← 返回申购记录</n-button>
    </div>

    <n-card title="申购记录信息">
      <n-form label-placement="top" :disabled="!auth.can('purchase:write')">
        <div class="form-grid">
          <n-form-item label="需求日期" required>
            <n-date-picker v-model:value="planDate" type="date" class="full-width" />
          </n-form-item>
          <n-form-item label="申购日期" required>
            <n-date-picker v-model:value="purchaseDate" type="date" class="full-width" />
          </n-form-item>
          <n-form-item label="申购单号">
            <n-input v-model:value="form.purchase_order_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="追溯号">
            <n-input v-model:value="form.trace_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="合同号">
            <n-input v-model:value="form.contract_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="船号">
            <n-input v-model:value="form.vessel_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="集港日期">
            <n-date-picker
              v-model:value="consolidationDate"
              type="date"
              class="full-width"
              clearable
            />
          </n-form-item>
          <n-form-item label="集港港口">
            <n-input v-model:value="form.consolidation_port" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="发船日期">
            <n-date-picker v-model:value="sailingDate" type="date" class="full-width" clearable />
          </n-form-item>
          <n-form-item label="物料编码">
            <n-input v-model:value="form.material_code" maxlength="64" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="类别">
            <n-select
              v-model:value="form.category"
              :options="purchaseCategoryOptions"
              filterable
              clearable
              placeholder="选择类别"
            />
          </n-form-item>
          <n-form-item label="需求部门" required>
            <n-input v-model:value="form.demand_department" maxlength="128" />
          </n-form-item>
          <n-form-item label="名称" required>
            <n-input v-model:value="form.material_name" maxlength="128" />
          </n-form-item>
          <n-form-item label="型号规格" required>
            <n-input v-model:value="form.model_spec" maxlength="255" />
          </n-form-item>
          <n-form-item label="申购数量 / 计量单位" required>
            <NInputGroup>
              <QuantityInput
                v-model:value="form.purchase_qty"
                :decimal-places="1"
                class="quantity-input"
              />
              <n-select
                v-model:value="form.unit_id"
                :options="dictionaries.unitOptions"
                class="quantity-unit-select"
              />
            </NInputGroup>
          </n-form-item>
          <n-form-item label="实际需求人" required>
            <n-input v-model:value="form.actual_demand_person" maxlength="128" />
          </n-form-item>
          <n-form-item label="申购负责人" required>
            <n-input v-model:value="form.purchase_responsible" maxlength="128" />
          </n-form-item>
          <n-form-item label="业务员">
            <n-input v-model:value="form.salesperson" maxlength="128" />
          </n-form-item>
          <n-form-item label="状态" required>
            <n-input v-model:value="form.status" maxlength="128" placeholder="可填写任意状态" />
          </n-form-item>
          <n-form-item label="子项号">
            <n-input v-model:value="form.subitem_no" maxlength="64" placeholder="选填" />
          </n-form-item>
          <n-form-item label="用途" required>
            <n-input v-model:value="form.usage" maxlength="500" />
          </n-form-item>
          <n-form-item label="关联二级库物资" class="wide-form-item">
            <MaterialSelector
              :value="form.stock_material_id ?? null"
              @update:value="form.stock_material_id = $event ?? undefined"
            />
          </n-form-item>
          <n-form-item label="申购计划备注">
            <n-input v-model:value="form.plan_remark" type="textarea" maxlength="1000" show-count />
          </n-form-item>
          <n-form-item label="申购记录备注">
            <n-input
              v-model:value="form.record_remark"
              type="textarea"
              maxlength="1000"
              show-count
            />
          </n-form-item>
          <n-form-item label="图片附件" class="wide-form-item attachment-form-item">
            <ImageUploader v-model:files="images" />
          </n-form-item>
        </div>
      </n-form>
      <template #footer>
        <n-space justify="space-between">
          <span class="muted">最后更新：{{ formatShanghaiTime(record.updated_at) }}</span>
          <n-button v-if="auth.can('purchase:write')" type="primary" :loading="saving" @click="save"
            >保存修改</n-button
          >
        </n-space>
      </template>
    </n-card>
  </div>
</template>

<style scoped>
.quantity-input {
  flex: 1;
}

.quantity-unit-select {
  width: 160px;
}

.wide-form-item {
  grid-column: 1 / -1;
}

.attachment-form-item {
  margin-bottom: 0;
}
</style>
