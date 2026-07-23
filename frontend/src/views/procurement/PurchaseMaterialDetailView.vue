<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import type { FileObject, PurchaseMaterial, PurchaseMaterialWrite } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'
import { defaultPurchasePlanStatus, purchasePlanStatusOptions } from '@/constants/purchase'
import MaterialSelector from '@/components/MaterialSelector.vue'
import { dateToTimestamp, formatShanghaiTime, toShanghaiDate } from '@/utils/time'
import { useDictionaryStore } from '@/stores/dictionaries'
import ImageUploader from '@/components/ImageUploader.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import { defaultPurchaseOrderNo } from '@/utils/purchase'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const dialog = useDialog()
const dictionaries = useDictionaryStore()
const material = ref<PurchaseMaterial | null>(null)
const loading = ref(true)
const saving = ref(false)
const deleting = ref(false)
const showMove = ref(false)
const moving = ref(false)
const moveForm = reactive({
  purchase_order_no: defaultPurchaseOrderNo(),
  trace_no: '',
  purchase_date: Date.now(),
  salesperson: '',
  status: '已申购',
  record_remark: '',
})
const images = ref<FileObject[]>([])
const planDate = ref<number | null>(null)
const form = reactive<PurchaseMaterialWrite>({
  status: defaultPurchasePlanStatus,
  material_code: '',
  name: '',
  model_spec: '',
  unit_id: null,
  actual_demand_person: '',
  purchase_responsible: '',
  planned_qty: '',
  usage: '',
  subitem_no: '',
  stock_material_id: undefined,
  remark: '',
  image_ids: [],
})
async function load() {
  loading.value = true
  try {
    material.value = await procurementApi.material(Number(route.params.id))
    syncForm(material.value)
  } finally {
    loading.value = false
  }
}
function syncForm(value: PurchaseMaterial) {
  Object.assign(form, {
    status: value.status,
    material_code: value.material_code || '',
    name: value.name,
    model_spec: value.model_spec,
    unit_id: value.unit_id,
    actual_demand_person: value.actual_demand_person,
    purchase_responsible: value.purchase_responsible,
    planned_qty: value.planned_qty,
    usage: value.usage,
    subitem_no: value.subitem_no || '',
    remark: value.remark || '',
    stock_material_id: value.stock_material_id,
    image_ids: value.images.map((image) => image.id),
    version: value.version,
  })
  planDate.value = dateToTimestamp(value.plan_date)
  images.value = [...value.images]
}
async function save() {
  if (
    !material.value ||
    !form.name.trim() ||
    !form.model_spec.trim() ||
    !form.unit_id ||
    !form.actual_demand_person?.trim() ||
    !form.purchase_responsible?.trim() ||
    !form.planned_qty ||
    !form.usage.trim() ||
    !planDate.value
  ) {
    message.error('请完整填写需求日期、物资、数量、用途、实际需求人和申购负责人')
    return
  }
  saving.value = true
  try {
    form.image_ids = images.value.map((image) => image.id)
    material.value = await procurementApi.updateMaterial(material.value.id, {
      ...form,
      plan_date: toShanghaiDate(planDate.value),
      subitem_no: form.subitem_no?.trim() || undefined,
    })
    syncForm(material.value)
    message.success('申购计划已保存')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}
async function deletePlan() {
  if (!material.value) return
  deleting.value = true
  try {
    await procurementApi.deleteMaterial(material.value.id, material.value.version)
    message.success('申购计划已删除')
    await router.push('/procurement/materials')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '删除失败')
  } finally {
    deleting.value = false
  }
}
function confirmDelete() {
  if (!material.value) return
  if (material.value.moved_to_record) {
    message.warning('已转入申购记录的计划不能删除')
    return
  }
  dialog.warning({
    title: '删除申购计划',
    content: `确认删除“${material.value.name}”的这条申购计划吗？删除后不可恢复。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: deletePlan,
  })
}
function openMove() {
  Object.assign(moveForm, {
    purchase_order_no: defaultPurchaseOrderNo(),
    trace_no: '',
    purchase_date: Date.now(),
    salesperson: '',
    status: '已申购',
    record_remark: '',
  })
  showMove.value = true
}
async function moveToRecord() {
  if (!material.value || !moveForm.purchase_date) {
    message.error('请选择申购日期')
    return
  }
  moving.value = true
  try {
    const record = await procurementApi.movePlanToRecord(material.value.id, {
      purchase_order_no: moveForm.purchase_order_no.trim() || null,
      trace_no: moveForm.trace_no.trim() || null,
      purchase_date: toShanghaiDate(moveForm.purchase_date),
      salesperson: moveForm.salesperson || undefined,
      status: moveForm.status.trim(),
      record_remark: moveForm.record_remark || undefined,
    })
    message.success('已转入申购记录')
    showMove.value = false
    await router.push(`/procurement/records/${record.line_id}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '转入失败')
  } finally {
    moving.value = false
  }
}
onMounted(() => {
  void dictionaries.load()
  void load()
})
</script>

<template>
  <div v-if="material" v-loading="loading" class="page">
    <div class="detail-toolbar">
      <n-button secondary @click="router.push('/procurement/materials')">← 返回申购计划</n-button>
      <n-space v-if="auth.can('purchase:write')">
        <n-button
          type="error"
          ghost
          :loading="deleting"
          :disabled="material.moved_to_record"
          @click="confirmDelete"
          >删除计划</n-button
        >
        <n-button v-if="material.material_code && !material.moved_to_record" @click="openMove"
          >转入申购记录</n-button
        >
      </n-space>
    </div>
    <n-card title="申购计划信息">
      <n-form label-placement="top" :disabled="!auth.can('purchase:write')">
        <div class="form-grid">
          <n-form-item label="计划 ID">
            <n-input :value="material.plan_no" disabled />
          </n-form-item>
          <n-form-item label="状态" required>
            <n-select v-model:value="form.status" :options="purchasePlanStatusOptions" />
          </n-form-item>
          <n-form-item label="需求日期" required>
            <n-date-picker v-model:value="planDate" type="date" class="full-width" />
          </n-form-item>
          <n-form-item label="物料编码">
            <n-input v-model:value="form.material_code" maxlength="64" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="名称" required>
            <n-input v-model:value="form.name" maxlength="128" />
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
          <n-form-item label="计划数量" required>
            <QuantityInput v-model:value="form.planned_qty" :decimal-places="1" />
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
        <n-form-item label="备注">
          <n-input v-model:value="form.remark" type="textarea" maxlength="1000" show-count />
        </n-form-item>
        <n-form-item label="图片附件"><ImageUploader v-model:files="images" /></n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="space-between">
          <span class="muted">最后更新：{{ formatShanghaiTime(material.updated_at) }}</span>
          <n-button v-if="auth.can('purchase:write')" type="primary" :loading="saving" @click="save"
            >保存修改</n-button
          >
        </n-space>
      </template>
    </n-card>
    <n-modal
      v-model:show="showMove"
      preset="card"
      title="转入申购记录"
      style="width: 560px"
      :mask-closable="false"
    >
      <n-alert type="info" style="margin-bottom: 16px"
        >计划信息将带入申购记录，转入后仍可继续修改和整理。</n-alert
      >
      <n-form label-placement="top">
        <div class="form-grid">
          <n-form-item label="申购单号">
            <n-input
              v-model:value="moveForm.purchase_order_no"
              maxlength="128"
              placeholder="可留空"
            />
          </n-form-item>
          <n-form-item label="追溯号">
            <n-input v-model:value="moveForm.trace_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="申购日期" required>
            <n-date-picker v-model:value="moveForm.purchase_date" type="date" class="full-width" />
          </n-form-item>
          <n-form-item label="业务员">
            <n-input v-model:value="moveForm.salesperson" maxlength="128" />
          </n-form-item>
          <n-form-item label="状态" required>
            <n-input v-model:value="moveForm.status" maxlength="128" />
          </n-form-item>
        </div>
        <n-form-item label="记录备注"
          ><n-input
            v-model:value="moveForm.record_remark"
            type="textarea"
            maxlength="1000"
            show-count
        /></n-form-item>
      </n-form>
      <template #footer
        ><n-space justify="end"
          ><n-button @click="showMove = false">取消</n-button
          ><n-button type="primary" :loading="moving" @click="moveToRecord"
            >确认转入</n-button
          ></n-space
        ></template
      >
    </n-modal>
  </div>
</template>
