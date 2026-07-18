<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
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
import QuantityInput from '@/components/QuantityInput.vue'
import { defaultPurchaseRequestNo } from '@/utils/purchase'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const dialog = useDialog()
const dictionaries = useDictionaryStore()
const material = ref<PurchaseMaterial | null>(null)
const loading = ref(true)
const showLink = ref(false)
const selectedStock = ref<number | null>(null)
const stockPreview = ref<StockMaterial | undefined>()
const showEdit = ref(false)
const saving = ref(false)
const deleting = ref(false)
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
  subitem_no: '',
  stock_material_id: undefined,
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
    subitem_no: material.value.subitem_no || '',
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
    !form.usage.trim()
  ) {
    message.error('请完整填写物资、数量、用途、实际需求人和申购负责人')
    return
  }
  saving.value = true
  try {
    form.image_ids = images.value.map((image) => image.id)
    material.value = await procurementApi.updateMaterial(material.value.id, {
      ...form,
      subitem_no: form.subitem_no?.trim() || undefined,
    })
    message.success('申购计划已保存')
    showEdit.value = false
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
    showEdit.value = false
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
        <n-space class="page-subtitle" size="small">
          <span>{{ material.material_code || '暂无物料编码' }}</span>
          <n-tag size="small" :type="material.moved_to_record ? 'success' : 'warning'">
            {{ material.moved_to_record ? '已转入申购记录' : '申购计划中' }}
          </n-tag>
        </n-space>
      </div>
      <n-space v-if="auth.can('purchase:write')"
        ><n-button @click="openEdit">编辑计划</n-button
        ><n-button v-if="!material.stock_material_id" @click="showLink = true"
          >关联二级库物资</n-button
        ><n-button
          v-if="material.material_code && !material.moved_to_record"
          type="primary"
          @click="showMove = true"
          >转入申购记录</n-button
        ></n-space
      >
    </div>
    <div class="detail-grid">
      <n-card title="物资信息">
        <n-descriptions :column="2" label-placement="left">
          <n-descriptions-item label="物料编码">{{
            material.material_code || '—'
          }}</n-descriptions-item>
          <n-descriptions-item label="计量单位">{{ material.unit_name }}</n-descriptions-item>
          <n-descriptions-item label="型号规格" :span="2">{{
            material.model_spec
          }}</n-descriptions-item>
          <n-descriptions-item label="关联二级库">{{
            material.stock_material_name || '—'
          }}</n-descriptions-item>
          <n-descriptions-item label="子项号">{{ material.subitem_no || '—' }}</n-descriptions-item>
          <n-descriptions-item label="用途" :span="2">{{ material.usage }}</n-descriptions-item>
          <n-descriptions-item label="备注" :span="2">{{
            material.remark || '—'
          }}</n-descriptions-item>
        </n-descriptions>
        <n-divider>物资图片</n-divider>
        <div v-if="material.images.length" class="image-grid">
          <n-image
            v-for="img in material.images"
            :key="img.id"
            :src="img.url"
            width="128"
            height="128"
            object-fit="cover"
          />
        </div>
        <n-empty v-else description="暂无图片" size="small" />
      </n-card>
      <n-card title="计划概览" class="plan-summary-card">
        <div class="plan-quantity">
          <span class="muted">计划数量</span>
          <strong>{{ material.planned_qty }}</strong>
          <span>{{ material.unit_name }}</span>
        </div>
        <div class="plan-meta">
          <div>
            <span>实际需求人</span>
            <strong>{{ material.actual_demand_person }}</strong>
          </div>
          <div>
            <span>申购负责人</span>
            <strong>{{ material.purchase_responsible }}</strong>
          </div>
          <div>
            <span>更新时间</span>
            <strong>{{ formatShanghaiTime(material.updated_at) }}</strong>
          </div>
        </div>
      </n-card>
    </div>
    <n-modal v-model:show="showLink" preset="card" title="关联已有二级库物资" style="width: 600px"
      ><n-alert type="info"
        >同一二级库物资可以关联多条申购计划，请确认名称、规格和单位一致。</n-alert
      ><br /><MaterialSelector
        v-model:value="selectedStock"
        @select="stockPreview = $event"
      /><n-descriptions v-if="stockPreview" :column="2" style="margin-top: 16px"
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
          <n-form-item label="子项号"
            ><n-input v-model:value="form.subitem_no" maxlength="64" placeholder="选填"
          /></n-form-item>
        </div>
        <n-form-item label="关联二级库物资"
          ><MaterialSelector
            :value="form.stock_material_id ?? null"
            @update:value="form.stock_material_id = $event ?? undefined"
        /></n-form-item>
        <n-form-item label="用途" required
          ><n-input v-model:value="form.usage" maxlength="500"
        /></n-form-item>
        <n-form-item label="备注"
          ><n-input v-model:value="form.remark" type="textarea" maxlength="1000" show-count
        /></n-form-item>
        <n-form-item label="图片"><ImageUploader v-model:files="images" /></n-form-item>
      </n-form>
      <template #footer>
        <div class="edit-footer">
          <n-button
            type="error"
            ghost
            :loading="deleting"
            :disabled="material.moved_to_record"
            @click="confirmDelete"
          >
            删除该计划
          </n-button>
          <n-space>
            <n-button @click="showEdit = false">取消</n-button>
            <n-button type="primary" :loading="saving" @click="save">保存</n-button>
          </n-space>
        </div>
      </template>
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

<style scoped>
.plan-summary-card {
  background: linear-gradient(145deg, #f3faf6 0%, #ffffff 58%);
}
.plan-quantity {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 8px 0 24px;
}
.plan-quantity strong {
  color: #18a058;
  font-size: 36px;
  line-height: 1;
}
.plan-meta {
  display: grid;
  gap: 18px;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
}
.plan-meta > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.plan-meta span {
  color: #6b7280;
}
.plan-meta strong {
  text-align: right;
}
.image-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.edit-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
</style>
