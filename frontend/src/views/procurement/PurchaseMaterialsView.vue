<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NTag,
  useMessage,
  type DataTableBaseColumn,
  type DataTableColumns,
  type FormInst,
  type FormRules,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import type {
  FileObject,
  PurchaseFilterOptions,
  PurchaseMaterial,
  PurchaseMaterialWrite,
} from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionaries'
import ImageUploader from '@/components/ImageUploader.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import ColumnVisibilityPicker from '@/components/ColumnVisibilityPicker.vue'
import { defaultPurchaseOrderNo } from '@/utils/purchase'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'
import { formatDate, toShanghaiDate } from '@/utils/time'
import { downloadBlob } from '@/utils/download'

const router = useRouter()
const auth = useAuthStore()
const dictionaries = useDictionaryStore()
const message = useMessage()
const rowClickGuard = createTableRowClickGuard()
const items = ref<PurchaseMaterial[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
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
const filters = reactive({
  name: '',
  model_spec: '',
  actual_demand_person: null as string | null,
})
const filterOptions = ref<PurchaseFilterOptions>({
  actual_demand_persons: [],
  purchase_responsibles: [],
})
const actualDemandPersonOptions = computed(() =>
  filterOptions.value.actual_demand_persons.map((value) => ({ label: value, value })),
)
const batchForm = reactive({
  purchase_order_no: defaultPurchaseOrderNo(),
  trace_no: '',
  purchase_date: Date.now(),
  salesperson: '',
  status: '已申购',
  record_remark: '',
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
type PlanColumnKey =
  | 'plan_no'
  | 'plan_date'
  | 'material_code'
  | 'name'
  | 'model_spec'
  | 'unit_name'
  | 'planned_qty'
  | 'actual_demand_person'
  | 'purchase_responsible'

const availableColumns: Array<{
  key: PlanColumnKey
  label: string
  column: DataTableBaseColumn<PurchaseMaterial>
}> = [
  { key: 'plan_no', label: '计划 ID', column: { title: '计划 ID', key: 'plan_no', width: 175 } },
  {
    key: 'plan_date',
    label: '需求日期',
    column: {
      title: '需求日期',
      key: 'plan_date',
      width: 110,
      render: (row) => formatDate(row.plan_date),
    },
  },
  {
    key: 'material_code',
    label: '物料编码',
    column: {
      title: '物料编码',
      key: 'material_code',
      width: 140,
      render: (row) =>
        row.material_code ||
        h(NTag, { type: 'warning', size: 'small' }, { default: () => '暂无编码' }),
    },
  },
  { key: 'name', label: '名称', column: { title: '名称', key: 'name' } },
  { key: 'model_spec', label: '型号规格', column: { title: '型号规格', key: 'model_spec' } },
  {
    key: 'planned_qty',
    label: '计划数量',
    column: { title: '计划数量', key: 'planned_qty', width: 100 },
  },
  { key: 'unit_name', label: '单位', column: { title: '单位', key: 'unit_name', width: 70 } },
  {
    key: 'actual_demand_person',
    label: '实际需求人',
    column: {
      title: '实际需求人',
      key: 'actual_demand_person',
      width: 110,
      render: (row) => row.actual_demand_person || '\\',
    },
  },
  {
    key: 'purchase_responsible',
    label: '申购负责人',
    column: {
      title: '申购负责人',
      key: 'purchase_responsible',
      width: 110,
      render: (row) => row.purchase_responsible || '\\',
    },
  },
]
const visibleColumnKeys = ref<PlanColumnKey[]>(availableColumns.map((item) => item.key))
const fieldOptions = availableColumns.map((item) => ({ label: item.label, value: item.key }))
const columns = computed<DataTableColumns<PurchaseMaterial>>(() => [
  {
    type: 'selection',
    disabled: (row) => !auth.can('purchase:write') || !row.material_code,
  },
  ...availableColumns
    .filter((item) => visibleColumnKeys.value.includes(item.key))
    .map((item) => item.column),
])
function setVisibleColumnKeys(value: string[]) {
  visibleColumnKeys.value = value as PlanColumnKey[]
}
function rowProps(row: PurchaseMaterial) {
  return {
    style: 'cursor: pointer',
    onMousedown: rowClickGuard.onMouseDown,
    onClick: (event: MouseEvent) => {
      if (rowClickGuard.shouldIgnore(event)) return
      void router.push(`/procurement/materials/${row.id}`)
    },
  }
}
async function load() {
  loading.value = true
  try {
    const d = await procurementApi.materials({
      page: page.value,
      page_size: pageSize.value,
      moved: false,
      name: filters.name.trim() || undefined,
      model_spec: filters.model_spec.trim() || undefined,
      actual_demand_person: filters.actual_demand_person?.trim() || undefined,
    })
    items.value = d.items
    total.value = d.total
    checkedRowKeys.value = []
  } finally {
    loading.value = false
  }
}
async function loadFilterOptions() {
  filterOptions.value = await procurementApi.materialFilterOptions({ moved: false })
}
function query() {
  page.value = 1
  void load()
}
function resetFilters() {
  filters.name = ''
  filters.model_spec = ''
  filters.actual_demand_person = null
  query()
}
function changePageSize() {
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
    message.error('请选择需求日期')
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
    await Promise.all([load(), loadFilterOptions()])
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
    status: '已申购',
    record_remark: '',
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
        status: batchForm.status.trim(),
        record_remark: batchForm.record_remark.trim() || undefined,
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
  void loadFilterOptions()
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
          v-model:value="filters.name"
          placeholder="名称"
          clearable
          style="width: 200px"
          @keyup.enter="query"
        />
        <n-input
          v-model:value="filters.model_spec"
          placeholder="型号"
          clearable
          style="width: 200px"
          @keyup.enter="query"
        />
        <n-select
          v-model:value="filters.actual_demand_person"
          :options="actualDemandPersonOptions"
          placeholder="实际需求人"
          filterable
          clearable
          style="width: 180px"
        />
        <ColumnVisibilityPicker
          :value="visibleColumnKeys"
          :options="fieldOptions"
          storage-key="procurement.purchase-materials.visible-columns.v1"
          @update:value="setVisibleColumnKeys"
        />
        <n-button type="primary" @click="query">查询</n-button>
        <n-button @click="resetFilters">重置</n-button>
      </div></n-card
    ><n-card
      ><n-data-table
        v-model:checked-row-keys="checkedRowKeys"
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-props="rowProps"
        :row-key="(r: PurchaseMaterial) => r.id" />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :item-count="total"
          :page-sizes="[10, 20, 50, 100, 200]"
          show-size-picker
          @update:page="load"
          @update:page-size="changePageSize"
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
          <n-form-item label="状态" required>
            <n-input v-model:value="batchForm.status" maxlength="128" />
          </n-form-item>
        </div>
        <n-form-item label="记录备注">
          <n-input
            v-model:value="batchForm.record_remark"
            type="textarea"
            maxlength="1000"
            show-count
          />
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
          ><n-form-item label="需求日期" required
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
