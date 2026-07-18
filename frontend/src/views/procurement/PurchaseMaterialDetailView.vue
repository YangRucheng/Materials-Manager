<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import type {
  FileObject,
  PurchaseMaterial,
  PurchaseMaterialWrite,
  StockMaterial,
} from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'
import MaterialSelector from '@/components/MaterialSelector.vue'
import { formatShanghaiTime } from '@/utils/time'
import { useDictionaryStore } from '@/stores/dictionaries'
import ImageUploader from '@/components/ImageUploader.vue'
import ProjectSubitemSelector from '@/components/ProjectSubitemSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import { defaultPurchaseRequestNo } from '@/utils/purchase'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const dictionaries = useDictionaryStore()
const material = ref<PurchaseMaterial | null>(null)
const loading = ref(true)
const showLink = ref(false)
const selectedStock = ref<number | null>(null)
const stockPreview = ref<StockMaterial | undefined>()
const showEdit = ref(false)
const saving = ref(false)
const showMove = ref(false)
const moving = ref(false)
const moveForm = reactive({ request_no: defaultPurchaseRequestNo(), salesperson: '', remark: '' })
const images = ref<FileObject[]>([])
const form = reactive<PurchaseMaterialWrite>({
  material_code: '',
  name: '',
  model_spec: '',
  unit_id: null,
  actual_demand_person: '',
  purchase_responsible: '',
  planned_qty: '',
  usage: '',
  project_subitem_id: undefined,
  remark: '',
  image_ids: [],
})
async function load() {
  loading.value = true
  try {
    material.value = await procurementApi.material(Number(route.params.id))
  } finally {
    loading.value = false
  }
}
async function linkStock() {
  if (!material.value || !selectedStock.value) return
  try {
    material.value = await procurementApi.linkStock(material.value.id, selectedStock.value)
    message.success('已关联二级库物资')
    showLink.value = false
  } catch (e) {
    message.error(e instanceof Error ? e.message : '关联失败')
  }
}
function openEdit() {
  if (!material.value) return
  Object.assign(form, {
    material_code: material.value.material_code || '',
    name: material.value.name,
    model_spec: material.value.model_spec,
    unit_id: material.value.unit_id,
    actual_demand_person: material.value.actual_demand_person,
    purchase_responsible: material.value.purchase_responsible,
    planned_qty: material.value.planned_qty,
    usage: material.value.usage,
    project_subitem_id: material.value.project_subitem_id,
    remark: material.value.remark || '',
    stock_material_id: material.value.stock_material_id,
    image_ids: material.value.images.map((image) => image.id),
    version: material.value.version,
  })
  images.value = [...material.value.images]
  showEdit.value = true
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
    !form.project_subitem_id
  ) {
    message.error('请完整填写物资、数量、用途、项目和申购负责人')
    return
  }
  saving.value = true
  try {
    form.image_ids = images.value.map((image) => image.id)
    material.value = await procurementApi.updateMaterial(material.value.id, form)
    message.success('申购计划已保存')
    showEdit.value = false
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}
async function moveToRecord() {
  if (!material.value || !moveForm.request_no.trim()) {
    message.error('请填写申购记录号')
    return
  }
  moving.value = true
  try {
    const record = await procurementApi.movePlanToRecord(material.value.id, {
      request_no: moveForm.request_no,
      salesperson: moveForm.salesperson || undefined,
      remark: moveForm.remark || undefined,
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
    <div class="page-header">
      <div>
        <n-button text @click="router.back()">← 返回申购计划</n-button>
        <h1 class="page-title">{{ material.name }}</h1>
        <p class="page-subtitle">{{ material.material_code || '暂无物料编码' }}</p>
      </div>
      <n-space v-if="auth.can('purchase:write')"
        ><n-button @click="openEdit">编辑计划</n-button
        ><n-button v-if="!material.stock_material_id" @click="showLink = true"
          >关联二级库物资</n-button
        ><n-button v-if="material.code_state === 'UNCODED'" type="primary" @click="openEdit"
          >补充编码</n-button
        ><n-button
          v-if="material.code_state === 'CODED' && !material.moved_to_record"
          type="primary"
          @click="showMove = true"
          >转入申购记录</n-button
        ></n-space
      >
    </div>
    <n-card title="物资信息"
      ><n-descriptions :column="3"
        ><n-descriptions-item label="物料编码">{{
          material.material_code || '—'
        }}</n-descriptions-item
        ><n-descriptions-item label="名称">{{ material.name }}</n-descriptions-item
        ><n-descriptions-item label="型号规格">{{ material.model_spec }}</n-descriptions-item
        ><n-descriptions-item label="单位">{{ material.unit_name }}</n-descriptions-item
        ><n-descriptions-item label="实际需求人">{{
          material.actual_demand_person
        }}</n-descriptions-item
        ><n-descriptions-item label="申购负责人">{{
          material.purchase_responsible
        }}</n-descriptions-item
        ><n-descriptions-item label="计划数量"
          >{{ material.planned_qty }} {{ material.unit_name }}</n-descriptions-item
        ><n-descriptions-item label="用途">{{ material.usage }}</n-descriptions-item
        ><n-descriptions-item label="项目子项">{{
          material.project_subitem_name || '—'
        }}</n-descriptions-item
        ><n-descriptions-item label="编码状态"
          ><n-tag :type="material.code_state === 'CODED' ? 'success' : 'warning'">{{
            material.code_state
          }}</n-tag></n-descriptions-item
        ><n-descriptions-item label="关联二级库">{{
          material.stock_material_name || '—'
        }}</n-descriptions-item
        ><n-descriptions-item label="更新时间">{{
          formatShanghaiTime(material.updated_at)
        }}</n-descriptions-item
        ><n-descriptions-item label="备注" :span="2">{{
          material.remark || '—'
        }}</n-descriptions-item></n-descriptions
      ><n-divider>图片</n-divider
      ><n-space v-if="material.images.length"
        ><n-image
          v-for="img in material.images"
          :key="img.id"
          :src="img.url"
          width="120"
          height="120"
          object-fit="cover" /></n-space
      ><n-empty v-else description="暂无图片"
    /></n-card>
    <n-modal v-model:show="showLink" preset="card" title="关联已有二级库物资" style="width: 600px"
      ><n-alert type="info"
        >同一二级库物资可以关联多条申购计划，请确认名称、规格和单位一致。</n-alert
      ><br /><MaterialSelector
        v-model:value="selectedStock"
        @select="stockPreview = $event"
      /><n-descriptions v-if="stockPreview" bordered :column="2" style="margin-top: 16px"
        ><n-descriptions-item label="名称">{{ stockPreview.name }}</n-descriptions-item
        ><n-descriptions-item label="规格">{{ stockPreview.model_spec }}</n-descriptions-item
        ><n-descriptions-item label="单位">{{ stockPreview.unit_name }}</n-descriptions-item
        ><n-descriptions-item label="库存">{{
          stockPreview.current_qty
        }}</n-descriptions-item></n-descriptions
      ><template #footer
        ><n-space justify="end"
          ><n-button @click="showLink = false">取消</n-button
          ><n-button type="primary" :disabled="!selectedStock" @click="linkStock"
            >确认关联</n-button
          ></n-space
        ></template
      ></n-modal
    >
    <n-modal
      v-model:show="showEdit"
      preset="card"
      title="编辑申购计划"
      style="width: 680px"
      :mask-closable="false"
    >
      <n-form label-placement="top">
        <div class="form-grid">
          <n-form-item label="物料编码"
            ><n-input v-model:value="form.material_code" maxlength="64"
          /></n-form-item>
          <n-form-item label="名称" required
            ><n-input v-model:value="form.name" maxlength="128"
          /></n-form-item>
          <n-form-item label="型号规格" required
            ><n-input v-model:value="form.model_spec" maxlength="255"
          /></n-form-item>
          <n-form-item label="计量单位" required
            ><n-select v-model:value="form.unit_id" :options="dictionaries.unitOptions"
          /></n-form-item>
          <n-form-item label="实际需求人" required
            ><n-input
              v-model:value="form.actual_demand_person"
              maxlength="128"
              placeholder="填写提出实际需求的员工"
          /></n-form-item>
          <n-form-item label="申购负责人" required
            ><n-input v-model:value="form.purchase_responsible" maxlength="128"
          /></n-form-item>
          <n-form-item label="计划数量" required
            ><QuantityInput v-model:value="form.planned_qty" :decimal-places="1"
          /></n-form-item>
          <n-form-item label="项目子项" required
            ><ProjectSubitemSelector
              :value="form.project_subitem_id ?? null"
              @update:value="form.project_subitem_id = $event ?? undefined"
          /></n-form-item>
        </div>
        <n-form-item label="用途" required
          ><n-input v-model:value="form.usage" maxlength="500"
        /></n-form-item>
        <n-form-item label="备注"
          ><n-input v-model:value="form.remark" type="textarea" maxlength="1000" show-count
        /></n-form-item>
        <n-form-item label="图片"><ImageUploader v-model:files="images" /></n-form-item>
      </n-form>
      <template #footer
        ><n-space justify="end"
          ><n-button @click="showEdit = false">取消</n-button
          ><n-button type="primary" :loading="saving" @click="save">保存</n-button></n-space
        ></template
      >
    </n-modal>
    <n-modal
      v-model:show="showMove"
      preset="card"
      title="转入申购记录"
      style="width: 560px"
      :mask-closable="false"
    >
      <n-alert type="info" style="margin-bottom: 16px"
        >表示已在公司系统正式提交申购；物资和计划数量会锁定带入到货跟踪。</n-alert
      >
      <n-form label-placement="top">
        <n-form-item label="申购记录号" required
          ><n-input v-model:value="moveForm.request_no" maxlength="128"
        /></n-form-item>
        <n-form-item label="业务员"
          ><n-input v-model:value="moveForm.salesperson" maxlength="128"
        /></n-form-item>
        <n-form-item label="跟踪备注"
          ><n-input v-model:value="moveForm.remark" type="textarea" maxlength="1000" show-count
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
