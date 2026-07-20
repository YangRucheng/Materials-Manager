<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NTag,
  useMessage,
  type DataTableColumns,
  type FormInst,
  type FormRules,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import type { FileObject, PurchaseMaterial, PurchaseMaterialWrite } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionaries'
import ImageUploader from '@/components/ImageUploader.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import { defaultPurchaseOrderNo } from '@/utils/purchase'
import { formatDate, toShanghaiDate } from '@/utils/time'
import { downloadBlob } from '@/utils/download'

const router = useRouter()
const auth = useAuthStore()
const dictionaries = useDictionaryStore()
const message = useMessage()
const items = ref<PurchaseMaterial[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const show = ref(false)
const showBatch = ref(false)
const saving = ref(false)
const batchMoving = ref(false)
const batchExporting = ref(false)
const checkedRowKeys = ref<Array<string | number>>([])
const formRef = ref<FormInst | null>(null)
const images = ref<FileObject[]>([])
const createPlanDate = ref(Date.now())
const filters = reactive({ keyword: '' })
const batchForm = reactive({
  purchase_order_no: defaultPurchaseOrderNo(),
  trace_no: '',
  purchase_date: Date.now(),
  salesperson: '',
  remark: '',
})
const selectedPlans = computed(() => {
  const selected = new Set(checkedRowKeys.value.map(Number))
  return items.value.filter((item) => selected.has(item.id))
})
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
const rules: FormRules = {
  name: { required: true, message: '请输入名称' },
  model_spec: { required: true, message: '请输入型号规格' },
  unit_id: { type: 'number', required: true, message: '请选择单位' },
  actual_demand_person: { required: true, message: '请输入实际需求人' },
  purchase_responsible: { required: true, message: '请输入申购负责人' },
  planned_qty: { required: true, message: '请输入计划数量' },
  usage: { required: true, message: '请输入用途' },
}
const columns: DataTableColumns<PurchaseMaterial> = [
  {
    type: 'selection',
    disabled: (row) => !auth.can('purchase:write') || !row.material_code,
  },
  { title: '计划 ID', key: 'plan_no', width: 175 },
  {
    title: '计划日期',
    key: 'plan_date',
    width: 110,
    render: (row) => formatDate(row.plan_date),
  },
  {
    title: '物料编码',
    key: 'material_code',
    width: 140,
    render: (r) =>
      r.material_code || h(NTag, { type: 'warning', size: 'small' }, { default: () => '暂无编码' }),
  },
  {
    title: '名称',
    key: 'name',
    render: (r) =>
      h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: () => router.push(`/procurement/materials/${r.id}`),
        },
        { default: () => r.name },
      ),
  },
  { title: '型号规格', key: 'model_spec' },
  { title: '单位', key: 'unit_name', width: 70 },
  { title: '计划数量', key: 'planned_qty', width: 100 },
  { title: '实际需求人', key: 'actual_demand_person', width: 110 },
  { title: '申购负责人', key: 'purchase_responsible', width: 110 },
  {
    title: '操作',
    key: 'action',
    width: 90,
    render: (r) =>
      h('div', { class: 'action-row' }, [
        h(
          NButton,
          { size: 'small', onClick: () => router.push(`/procurement/materials/${r.id}`) },
          { default: () => (auth.can('purchase:write') ? '编辑' : '查看') },
        ),
      ]),
  },
]
async function load() {
  loading.value = true
  try {
    const d = await procurementApi.materials({
      page: page.value,
      page_size: 20,
      moved: false,
      ...filters,
    })
    items.value = d.items
    total.value = d.total
    checkedRowKeys.value = []
  } finally {
    loading.value = false
  }
}
function query() {
  page.value = 1
  void load()
}
function openCreate() {
  Object.assign(form, {
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
  images.value = []
  createPlanDate.value = Date.now()
  show.value = true
}
async function save() {
  if (!createPlanDate.value) {
    message.error('请选择计划日期')
    return
  }
  await formRef.value?.validate()
  saving.value = true
  try {
    form.image_ids = images.value.map((x) => x.id)
    await procurementApi.createMaterial({
      ...form,
      plan_date: toShanghaiDate(createPlanDate.value),
      subitem_no: form.subitem_no?.trim() || undefined,
    })
    message.success('申购计划已创建')
    show.value = false
    page.value = 1
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    saving.value = false
  }
}
function openBatchMove() {
  if (!selectedPlans.value.length) {
    message.warning('请先选择至少一条已有编码的申购计划')
    return
  }
  Object.assign(batchForm, {
    purchase_order_no: defaultPurchaseOrderNo(),
    trace_no: '',
    purchase_date: Date.now(),
    salesperson: '',
    remark: '',
  })
  showBatch.value = true
}
async function batchMove() {
  if (!batchForm.purchase_date) {
    message.error('请选择申购日期')
    return
  }
  batchMoving.value = true
  try {
    await procurementApi.batchMovePlansToRecord(
      selectedPlans.value.map((item) => item.id),
      {
        purchase_order_no: batchForm.purchase_order_no.trim() || null,
        trace_no: batchForm.trace_no.trim() || null,
        purchase_date: toShanghaiDate(batchForm.purchase_date),
        salesperson: batchForm.salesperson.trim() || undefined,
        remark: batchForm.remark.trim() || undefined,
      },
    )
    message.success(`已将 ${selectedPlans.value.length} 条计划转为申购记录`)
    checkedRowKeys.value = []
    showBatch.value = false
    await router.push('/procurement/records')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '批量转入失败')
  } finally {
    batchMoving.value = false
  }
}
async function exportPurchaseApplication() {
  if (!selectedPlans.value.length) return
  batchExporting.value = true
  try {
    const content = await procurementApi.exportPurchaseApplication(
      selectedPlans.value.map((item) => item.id),
    )
    downloadBlob(content, '采购申请.xlsx')
    message.success('采购申请表已导出')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    batchExporting.value = false
  }
}
onMounted(() => {
  void dictionaries.load()
  void load()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">申购计划</h1>
        <p class="page-subtitle">
          计划阶段确定物资、数量和用途，子项号按需填写，物料编码可暂时为空
        </p>
      </div>
      <n-space v-if="auth.can('purchase:write')">
        <n-button
          :disabled="!selectedPlans.length"
          :loading="batchExporting"
          @click="exportPurchaseApplication"
        >
          导出采购申请表（{{ selectedPlans.length }}）
        </n-button>
        <n-button :disabled="!selectedPlans.length" @click="openBatchMove">
          批量转为申购记录（{{ selectedPlans.length }}）
        </n-button>
        <n-button type="primary" @click="openCreate">新建申购计划</n-button>
      </n-space>
    </div>
    <n-card
      ><div class="filter-bar">
        <n-input
          v-model:value="filters.keyword"
          placeholder="计划 ID、编码、名称或规格"
          clearable
          style="width: 240px"
        /><n-button type="primary" @click="query">查询</n-button>
      </div></n-card
    ><n-card
      ><n-data-table
        v-model:checked-row-keys="checkedRowKeys"
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(r: PurchaseMaterial) => r.id" />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          :page-size="20"
          :item-count="total"
          @update:page="load"
        /></div
    ></n-card>
    <n-modal
      v-model:show="showBatch"
      preset="card"
      title="批量转为申购记录"
      style="width: 620px"
      :mask-closable="false"
    >
      <n-alert type="info" style="margin-bottom: 16px">
        已选择 {{ selectedPlans.length }} 条计划，将使用同一申购单号、追溯号和申购日期转入。
      </n-alert>
      <n-form label-placement="top">
        <div class="form-grid">
          <n-form-item label="申购单号">
            <n-input
              v-model:value="batchForm.purchase_order_no"
              maxlength="128"
              placeholder="可留空"
            />
          </n-form-item>
          <n-form-item label="追溯号">
            <n-input v-model:value="batchForm.trace_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="申购日期" required>
            <n-date-picker v-model:value="batchForm.purchase_date" type="date" class="full-width" />
          </n-form-item>
          <n-form-item label="业务员">
            <n-input v-model:value="batchForm.salesperson" maxlength="128" />
          </n-form-item>
        </div>
        <n-form-item label="备注">
          <n-input v-model:value="batchForm.remark" type="textarea" maxlength="1000" show-count />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showBatch = false">取消</n-button>
          <n-button type="primary" :loading="batchMoving" @click="batchMove">确认转入</n-button>
        </n-space>
      </template>
    </n-modal>
    <n-modal
      v-model:show="show"
      preset="card"
      title="新建申购计划"
      style="width: 680px"
      :mask-closable="false"
      ><n-form ref="formRef" :model="form" :rules="rules" label-placement="top"
        ><div class="form-grid">
          <n-form-item label="物料编码（已有时填写）"
            ><n-input
              v-model:value="form.material_code"
              maxlength="64"
              placeholder="没有编码可留空" /></n-form-item
          ><n-form-item label="计划日期" required
            ><n-date-picker
              v-model:value="createPlanDate"
              type="date"
              class="full-width" /></n-form-item
          ><n-form-item label="名称" path="name"
            ><n-input v-model:value="form.name" maxlength="128" /></n-form-item
          ><n-form-item label="型号规格" path="model_spec"
            ><n-input v-model:value="form.model_spec" maxlength="255" /></n-form-item
          ><n-form-item label="计量单位" path="unit_id"
            ><n-select
              v-model:value="form.unit_id"
              :options="dictionaries.unitOptions" /></n-form-item
          ><n-form-item label="实际需求人" path="actual_demand_person"
            ><n-input
              v-model:value="form.actual_demand_person"
              maxlength="128"
              placeholder="填写提出实际需求的员工" /></n-form-item
          ><n-form-item label="申购负责人" path="purchase_responsible"
            ><n-input v-model:value="form.purchase_responsible" maxlength="128"
          /></n-form-item>
          <n-form-item label="计划数量" path="planned_qty"
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
        <n-form-item label="用途" path="usage"
          ><n-input v-model:value="form.usage" maxlength="500"
        /></n-form-item>
        <n-form-item label="备注"
          ><n-input
            v-model:value="form.remark"
            type="textarea"
            maxlength="1000"
            show-count /></n-form-item
        ><n-form-item label="图片"><ImageUploader v-model:files="images" /></n-form-item></n-form
      ><template #footer
        ><n-space justify="end"
          ><n-button @click="show = false">取消</n-button
          ><n-button type="primary" :loading="saving" @click="save">保存</n-button></n-space
        ></template
      ></n-modal
    >
  </div>
</template>
