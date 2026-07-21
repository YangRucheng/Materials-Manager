<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import type { FileObject, PurchaseRecord, PurchaseRecordWrite } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionaries'
import ImageUploader from '@/components/ImageUploader.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import { dateToTimestamp, formatShanghaiTime, toShanghaiDate } from '@/utils/time'

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
const form = reactive<PurchaseRecordWrite>({
  plan_date: '',
  material_code: '',
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
    purchase_date: value.purchase_date || '',
    salesperson: value.salesperson || '',
    status: value.status,
    record_remark: value.record_remark || '',
    version: value.version,
  })
  planDate.value = dateToTimestamp(value.plan_date)
  purchaseDate.value = dateToTimestamp(value.purchase_date)
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
      material_code: form.material_code?.trim() || undefined,
      subitem_no: form.subitem_no?.trim() || undefined,
      plan_remark: form.plan_remark?.trim() || undefined,
      record_remark: form.record_remark?.trim() || undefined,
      purchase_order_no: form.purchase_order_no?.trim() || null,
      trace_no: form.trace_no?.trim() || null,
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
    <div class="page-header">
      <div>
        <n-button text @click="router.back()">← 返回申购记录</n-button>
        <h1 class="page-title">{{ record.material_name }}</h1>
        <p class="page-subtitle">{{ record.plan_no }} · {{ record.status }}</p>
      </div>
      <n-button v-if="auth.can('purchase:write')" type="primary" :loading="saving" @click="save"
        >保存修改</n-button
      >
    </div>

    <n-card title="申购计划信息">
      <n-form label-placement="top" :disabled="!auth.can('purchase:write')">
        <div class="form-grid">
          <n-form-item label="物料编码">
            <n-input v-model:value="form.material_code" maxlength="64" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="计划日期" required>
            <n-date-picker v-model:value="planDate" type="date" class="full-width" />
          </n-form-item>
          <n-form-item label="名称" required>
            <n-input v-model:value="form.material_name" maxlength="128" />
          </n-form-item>
          <n-form-item label="型号规格" required>
            <n-input v-model:value="form.model_spec" maxlength="255" />
          </n-form-item>
          <n-form-item label="计量单位" required>
            <n-select v-model:value="form.unit_id" :options="dictionaries.unitOptions" />
          </n-form-item>
          <n-form-item label="实际需求人" required>
            <n-input v-model:value="form.actual_demand_person" maxlength="128" />
          </n-form-item>
          <n-form-item label="申购负责人" required>
            <n-input v-model:value="form.purchase_responsible" maxlength="128" />
          </n-form-item>
          <n-form-item label="申购数量" required>
            <QuantityInput v-model:value="form.purchase_qty" :decimal-places="1" />
          </n-form-item>
          <n-form-item label="子项号">
            <n-input v-model:value="form.subitem_no" maxlength="64" placeholder="选填" />
          </n-form-item>
        </div>
        <n-form-item label="关联二级库物资">
          <MaterialSelector
            :value="form.stock_material_id ?? null"
            @update:value="form.stock_material_id = $event ?? undefined"
          />
        </n-form-item>
        <n-form-item label="用途" required>
          <n-input v-model:value="form.usage" maxlength="500" />
        </n-form-item>
        <n-form-item label="计划备注">
          <n-input v-model:value="form.plan_remark" type="textarea" maxlength="1000" show-count />
        </n-form-item>
        <n-form-item label="附件"><ImageUploader v-model:files="images" /></n-form-item>
      </n-form>
    </n-card>

    <n-card title="申购记录额外信息">
      <n-form label-placement="top" :disabled="!auth.can('purchase:write')">
        <div class="form-grid">
          <n-form-item label="申购单号">
            <n-input v-model:value="form.purchase_order_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="追溯号">
            <n-input v-model:value="form.trace_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="申购日期" required>
            <n-date-picker v-model:value="purchaseDate" type="date" class="full-width" />
          </n-form-item>
          <n-form-item label="业务员">
            <n-input v-model:value="form.salesperson" maxlength="128" />
          </n-form-item>
          <n-form-item label="状态" required>
            <n-input v-model:value="form.status" maxlength="128" placeholder="可填写任意状态" />
          </n-form-item>
        </div>
        <n-form-item label="记录备注">
          <n-input v-model:value="form.record_remark" type="textarea" maxlength="1000" show-count />
        </n-form-item>
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
