<script setup lang="ts">
import { computed, h, onActivated, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  NTag,
  useMessage,
  type DataTableBaseColumn,
  type DataTableColumns,
  type FormInst,
  type FormRules,
} from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import type {
  FileObject,
  PurchaseFilterOptions,
  PurchaseMaterial,
  PurchaseMaterialBatchUpdate,
  PurchasePlanStatus,
  PurchaseMaterialWrite,
} from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { aiSearchApi } from '@/api/aiSearch'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionaries'
import ImageUploader from '@/components/ImageUploader.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import ColumnVisibilityPicker from '@/components/ColumnVisibilityPicker.vue'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import {
  defaultPurchaseOrderNo,
  getLastPurchaseResponsible,
  rememberPurchaseResponsible,
} from '@/utils/purchase'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'
import {
  defaultPurchasePlanStatus,
  purchasePlanStatusFilterOptions,
  purchasePlanStatusOptions,
  type PurchasePlanStatusFilter,
} from '@/constants/purchase'
import { formatDate, toShanghaiDate } from '@/utils/time'
import { downloadBlob } from '@/utils/download'
import { compactRouteQuery, routeQueryPositiveInteger, routeQueryString } from '@/utils/routeQuery'
import { useImplicitAiSearch } from '@/composables/useImplicitAiSearch'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const dictionaries = useDictionaryStore()
const message = useMessage()
const rowClickGuard = createTableRowClickGuard()
const items = ref<PurchaseMaterial[]>([])
const total = ref(0)
const page = ref(routeQueryPositiveInteger(route.query.page, 1))
const pageSize = ref(routeQueryPositiveInteger(route.query.page_size, 20))
const loading = ref(false)
const aiAvailable = ref(false)
const aiSearching = ref(false)
const resultExporting = ref(false)
const show = ref(false)
const showBatch = ref(false)
const showBatchEdit = ref(false)
const saving = ref(false)
const batchMoving = ref(false)
const batchUpdating = ref(false)
const batchExporting = ref(false)
const checkedRowKeys = ref<Array<string | number>>([])
const tableAreaRef = ref<HTMLElement | null>(null)
const isTableFullscreen = ref(false)
const formRef = ref<FormInst | null>(null)
const images = ref<FileObject[]>([])
const createPlanDate = ref(Date.now())
const EMPTY_DEMAND_PERSON_FILTER = '__empty_actual_demand_person__'
const ALL_SUBITEM_FILTER = '__all_subitem_no__'
const EMPTY_SUBITEM_FILTER = '__empty_subitem_no__'
const routeStatus = routeQueryString(route.query.status)
const canViewArchivedPlans = computed(() => auth.user?.role === 'SUPER_ADMIN')
const statusFilterOptions = computed(() =>
  canViewArchivedPlans.value
    ? purchasePlanStatusFilterOptions
    : purchasePlanStatusFilterOptions.filter(
        (option) => option.value === defaultPurchasePlanStatus,
      ),
)
const filters = reactive({
  name: routeQueryString(route.query.name),
  model_spec: routeQueryString(route.query.model_spec),
  actual_demand_person: routeQueryString(route.query.actual_demand_person) || null,
  subitem_no: routeQueryString(route.query.subitem_no) || ALL_SUBITEM_FILTER,
  status: statusFilterOptions.value.some((option) => option.value === routeStatus)
    ? (routeStatus as PurchasePlanStatusFilter)
    : defaultPurchasePlanStatus,
})
const { searchName, applyExpandedName, clearExpandedName } = useImplicitAiSearch(() => filters.name)
const filterOptions = ref<PurchaseFilterOptions>({
  actual_demand_persons: [],
  purchase_responsibles: [],
  subitem_nos: [],
})
const actualDemandPersonOptions = computed(() => [
  { label: '空需求人', value: EMPTY_DEMAND_PERSON_FILTER },
  ...filterOptions.value.actual_demand_persons.map((value) => ({ label: value, value })),
])
const subitemOptions = computed(() => [
  { label: '全部子项号', value: ALL_SUBITEM_FILTER },
  { label: '空子项号', value: EMPTY_SUBITEM_FILTER },
  ...filterOptions.value.subitem_nos.map((value) => ({ label: value, value })),
])
const activeFilterCount = computed(
  () =>
    [
      filters.name.trim(),
      filters.model_spec.trim(),
      filters.actual_demand_person,
      filters.subitem_no === ALL_SUBITEM_FILTER ? '' : filters.subitem_no,
      filters.status === defaultPurchasePlanStatus ? '' : filters.status,
    ].filter(Boolean).length,
)
const batchForm = reactive({
  purchase_order_no: defaultPurchaseOrderNo(),
  trace_no: '',
  purchase_date: Date.now(),
  salesperson: '',
  status: '已申购',
  record_remark: '',
})
const batchEditForm = reactive({
  update_plan_date: false,
  plan_date: null as number | null,
  update_actual_demand_person: false,
  actual_demand_person: '',
  update_subitem_no: false,
  subitem_no: '',
  update_usage: false,
  usage: '',
  update_status: false,
  status: defaultPurchasePlanStatus as PurchasePlanStatus,
})
const selectedPlans = computed(() => {
  const selected = new Set(checkedRowKeys.value.map(Number))
  return items.value.filter((item) => selected.has(item.id))
})
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
  | 'subitem_no'
  | 'usage'

const availableColumns: Array<{
  key: PlanColumnKey
  label: string
  column: DataTableBaseColumn<PurchaseMaterial>
}> = [
  {
    key: 'plan_no',
    label: '计划 ID',
    column: { title: '计划 ID', key: 'plan_no', width: tableColumnWidths.identifier },
  },
  {
    key: 'plan_date',
    label: '需求日期',
    column: {
      title: '需求日期',
      key: 'plan_date',
      width: tableColumnWidths.date,
      render: (row) => formatDate(row.plan_date),
    },
  },
  {
    key: 'material_code',
    label: '物料编码',
    column: {
      title: '物料编码',
      key: 'material_code',
      width: tableColumnWidths.code,
      render: (row) =>
        row.material_code ||
        h(NTag, { type: 'warning', size: 'small' }, { default: () => '暂无编码' }),
    },
  },
  {
    key: 'name',
    label: '名称',
    column: {
      title: '名称',
      key: 'name',
      width: tableColumnWidths.name,
      ellipsis: { tooltip: true },
    },
  },
  {
    key: 'model_spec',
    label: '型号规格',
    column: {
      title: '型号规格',
      key: 'model_spec',
      width: tableColumnWidths.model,
      render: (row) =>
        h('div', { class: 'model-spec-clamp', title: row.model_spec }, row.model_spec),
    },
  },
  {
    key: 'planned_qty',
    label: '计划数量',
    column: { title: '计划数量', key: 'planned_qty', width: tableColumnWidths.quantity },
  },
  {
    key: 'unit_name',
    label: '单位',
    column: { title: '单位', key: 'unit_name', width: tableColumnWidths.unit },
  },
  {
    key: 'actual_demand_person',
    label: '实际需求人',
    column: {
      title: '实际需求人',
      key: 'actual_demand_person',
      width: tableColumnWidths.person,
      render: (row) => row.actual_demand_person || '\\',
    },
  },
  {
    key: 'purchase_responsible',
    label: '申购负责人',
    column: {
      title: '申购负责人',
      key: 'purchase_responsible',
      width: tableColumnWidths.person,
      render: (row) => row.purchase_responsible || '\\',
    },
  },
  {
    key: 'subitem_no',
    label: '子项号',
    column: {
      title: '子项号',
      key: 'subitem_no',
      width: tableColumnWidths.person,
      render: (row) => row.subitem_no || '\\',
    },
  },
  {
    key: 'usage',
    label: '用途',
    column: {
      title: '用途',
      key: 'usage',
      width: tableColumnWidths.text,
      ellipsis: { tooltip: true },
    },
  },
]
const visibleColumnKeys = ref<PlanColumnKey[]>(availableColumns.map((item) => item.key))
const fieldOptions = availableColumns.map((item) => ({ label: item.label, value: item.key }))
const columns = computed<DataTableColumns<PurchaseMaterial>>(() =>
  preventTableColumnCompression([
    {
      type: 'selection',
      disabled: () => !auth.can('purchase:write'),
    },
    ...availableColumns
      .filter((item) => visibleColumnKeys.value.includes(item.key))
      .map((item) => item.column),
  ]),
)
const tableScrollX = computed(() => getTableScrollX(columns.value))
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
function syncTableFullscreen() {
  isTableFullscreen.value = document.fullscreenElement === tableAreaRef.value
}
async function toggleTableFullscreen() {
  const tableArea = tableAreaRef.value
  if (!tableArea?.requestFullscreen) {
    message.warning('当前浏览器不支持全屏显示')
    return
  }
  try {
    if (document.fullscreenElement === tableArea) await document.exitFullscreen()
    else await tableArea.requestFullscreen()
  } catch {
    message.error('切换全屏失败')
  }
}
async function load() {
  loading.value = true
  try {
    const d = await procurementApi.materials({
      page: page.value,
      page_size: pageSize.value,
      moved: false,
      name: searchName.value,
      model_spec: filters.model_spec.trim() || undefined,
      actual_demand_person:
        filters.actual_demand_person && filters.actual_demand_person !== EMPTY_DEMAND_PERSON_FILTER
          ? filters.actual_demand_person.trim()
          : undefined,
      empty_actual_demand_person:
        filters.actual_demand_person === EMPTY_DEMAND_PERSON_FILTER || undefined,
      subitem_no:
        filters.subitem_no !== ALL_SUBITEM_FILTER && filters.subitem_no !== EMPTY_SUBITEM_FILTER
          ? filters.subitem_no
          : undefined,
      empty_subitem_no: filters.subitem_no === EMPTY_SUBITEM_FILTER || undefined,
      status: filters.status === '全部' ? undefined : filters.status,
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
async function loadAiStatus() {
  try {
    aiAvailable.value = (await aiSearchApi.status()).available
  } catch {
    aiAvailable.value = false
  }
}
async function syncRoute() {
  await router.replace({
    name: 'purchase-materials',
    query: compactRouteQuery({
      page: page.value === 1 ? undefined : page.value,
      page_size: pageSize.value === 20 ? undefined : pageSize.value,
      name: filters.name,
      model_spec: filters.model_spec,
      actual_demand_person: filters.actual_demand_person,
      subitem_no: filters.subitem_no === ALL_SUBITEM_FILTER ? undefined : filters.subitem_no,
      status: filters.status === defaultPurchasePlanStatus ? undefined : filters.status,
    }),
  })
}
async function syncRouteAndLoad(resetPage = false) {
  if (resetPage) page.value = 1
  await syncRoute()
  await load()
}
function query() {
  clearExpandedName()
  void syncRouteAndLoad(true)
}
async function aiQuery() {
  const value = filters.name.trim()
  if (!value) {
    message.warning('请先输入物资名称')
    return
  }
  aiSearching.value = true
  try {
    const data = await aiSearchApi.expand(value)
    applyExpandedName(data.expanded)
    await syncRouteAndLoad(true)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '智能查询失败')
  } finally {
    aiSearching.value = false
  }
}
async function exportResults() {
  const exportColumns = availableColumns
    .filter((item) => visibleColumnKeys.value.includes(item.key))
    .map((item) => item.key)
  if (!exportColumns.length) {
    message.warning('请至少显示一个字段')
    return
  }
  resultExporting.value = true
  try {
    const actualDemandPerson =
      filters.actual_demand_person && filters.actual_demand_person !== EMPTY_DEMAND_PERSON_FILTER
        ? filters.actual_demand_person.trim()
        : undefined
    const content = await procurementApi.exportMaterialResults({
      columns: exportColumns,
      name: searchName.value,
      model_spec: filters.model_spec.trim() || undefined,
      actual_demand_person: actualDemandPerson,
      empty_actual_demand_person: filters.actual_demand_person === EMPTY_DEMAND_PERSON_FILTER,
      subitem_no:
        filters.subitem_no !== ALL_SUBITEM_FILTER && filters.subitem_no !== EMPTY_SUBITEM_FILTER
          ? filters.subitem_no
          : undefined,
      empty_subitem_no: filters.subitem_no === EMPTY_SUBITEM_FILTER,
      status: filters.status === '全部' ? undefined : filters.status,
    })
    const date = toShanghaiDate(Date.now()).replace(/-/g, '')
    downloadBlob(content, `申购计划导出_${date}.xlsx`)
    message.success('查询结果已导出')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    resultExporting.value = false
  }
}
function resetFilters() {
  filters.name = ''
  filters.model_spec = ''
  filters.actual_demand_person = null
  filters.subitem_no = ALL_SUBITEM_FILTER
  filters.status = defaultPurchasePlanStatus
  query()
}
function changePageSize() {
  void syncRouteAndLoad(true)
}
function changePage() {
  void syncRouteAndLoad()
}
function openCreate() {
  Object.assign(form, {
    status: defaultPurchasePlanStatus,
    material_code: '',
    name: '',
    model_spec: '',
    unit_id: null,
    actual_demand_person: '',
    purchase_responsible: getLastPurchaseResponsible(),
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
    rememberPurchaseResponsible(form.purchase_responsible || '')
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
  if (selectedPlans.value.some((item) => !item.material_code)) {
    message.warning('选中的申购计划包含未编码物资，请先补充物料编码')
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
function openBatchEdit() {
  if (!selectedPlans.value.length) {
    message.warning('请先选择至少一条申购计划')
    return
  }
  Object.assign(batchEditForm, {
    update_plan_date: false,
    plan_date: null,
    update_actual_demand_person: false,
    actual_demand_person: '',
    update_subitem_no: false,
    subitem_no: '',
    update_usage: false,
    usage: '',
    update_status: false,
    status: defaultPurchasePlanStatus,
  })
  showBatchEdit.value = true
}
async function batchUpdate() {
  const payload: PurchaseMaterialBatchUpdate = {
    materials: selectedPlans.value.map((item) => ({ id: item.id, version: item.version })),
  }
  if (batchEditForm.update_plan_date) {
    if (!batchEditForm.plan_date) {
      message.error('请选择需求日期')
      return
    }
    payload.plan_date = toShanghaiDate(batchEditForm.plan_date)
  }
  if (batchEditForm.update_actual_demand_person) {
    if (!batchEditForm.actual_demand_person.trim()) {
      message.error('请输入实际需求人')
      return
    }
    payload.actual_demand_person = batchEditForm.actual_demand_person.trim()
  }
  if (batchEditForm.update_subitem_no) {
    payload.subitem_no = batchEditForm.subitem_no.trim() || null
  }
  if (batchEditForm.update_usage) {
    if (!batchEditForm.usage.trim()) {
      message.error('请输入用途')
      return
    }
    payload.usage = batchEditForm.usage.trim()
  }
  if (batchEditForm.update_status) {
    payload.status = batchEditForm.status
  }
  if (Object.keys(payload).length === 1) {
    message.warning('请至少勾选一个需要修改的字段')
    return
  }
  batchUpdating.value = true
  try {
    await procurementApi.batchUpdateMaterials(payload)
    message.success(`已批量修改 ${selectedPlans.value.length} 条申购计划`)
    showBatchEdit.value = false
    await Promise.all([load(), loadFilterOptions()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '批量修改失败')
  } finally {
    batchUpdating.value = false
  }
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
  if (selectedPlans.value.some((item) => !item.material_code)) {
    message.warning('选中的申购计划包含未编码物资，请先补充物料编码')
    return
  }
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
  document.addEventListener('fullscreenchange', syncTableFullscreen)
  void dictionaries.load()
  void loadFilterOptions()
  void loadAiStatus()
  void load()
})
onActivated(() => {
  void syncRoute()
})
onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', syncTableFullscreen)
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">申购计划</h1>
      </div>
      <n-space v-if="auth.can('purchase:write')">
        <n-button
          :disabled="!selectedPlans.length"
          :loading="batchExporting"
          @click="exportPurchaseApplication"
        >
          导出采购申请表（{{ selectedPlans.length }}）
        </n-button>
        <n-button :disabled="!selectedPlans.length" @click="openBatchEdit">
          批量修改（{{ selectedPlans.length }}）
        </n-button>
        <n-button :disabled="!selectedPlans.length" @click="openBatchMove">
          批量转为申购记录（{{ selectedPlans.length }}）
        </n-button>
        <n-button type="primary" @click="openCreate">新建申购计划</n-button>
      </n-space>
    </div>
    <n-card class="filter-card" :bordered="false">
      <div class="filter-heading">
        <div class="filter-title">筛选条件</div>
        <n-tag v-if="activeFilterCount" :bordered="false" round type="success">
          已启用 {{ activeFilterCount }} 项
        </n-tag>
      </div>
      <div class="purchase-plan-filter-grid">
        <label class="filter-field">
          <span>物资名称</span>
          <n-input
            v-model:value="filters.name"
            placeholder="输入物资名称"
            clearable
            @keyup.enter="query"
          />
        </label>
        <label class="filter-field">
          <span>型号规格</span>
          <n-input
            v-model:value="filters.model_spec"
            placeholder="输入型号规格"
            clearable
            @keyup.enter="query"
          />
        </label>
        <label class="filter-field">
          <span>实际需求人</span>
          <n-select
            v-model:value="filters.actual_demand_person"
            :options="actualDemandPersonOptions"
            placeholder="选择或搜索需求人"
            filterable
            clearable
          />
        </label>
        <label class="filter-field">
          <span>子项号</span>
          <n-select v-model:value="filters.subitem_no" :options="subitemOptions" filterable />
        </label>
        <label class="filter-field">
          <span>计划状态</span>
          <n-select v-model:value="filters.status" :options="statusFilterOptions" />
        </label>
      </div>
      <div class="filter-actions">
        <ColumnVisibilityPicker
          :value="visibleColumnKeys"
          :options="fieldOptions"
          storage-key="procurement.purchase-materials.visible-columns.v2"
          @update:value="setVisibleColumnKeys"
        />
        <div class="filter-action-buttons">
          <n-button @click="resetFilters">重置</n-button>
          <n-button :loading="resultExporting" @click="exportResults">导出结果</n-button>
          <n-button
            secondary
            type="primary"
            :loading="aiSearching"
            :disabled="!aiAvailable || !filters.name.trim()"
            :title="
              aiAvailable
                ? filters.name.trim()
                  ? '自动扩展物资名称同义词并立即查询'
                  : '请先输入物资名称'
                : '请联系超级管理员配置大模型服务'
            "
            @click="aiQuery"
          >
            智能查询
          </n-button>
          <n-button type="primary" @click="query">查询</n-button>
        </div>
      </div>
    </n-card>
    <div ref="tableAreaRef" class="purchase-plan-table-area">
      <n-button
        class="table-fullscreen-toggle"
        :class="{ 'is-fullscreen': isTableFullscreen }"
        quaternary
        circle
        size="small"
        :title="isTableFullscreen ? '退出表格全屏' : '表格全屏'"
        :aria-label="isTableFullscreen ? '退出表格全屏' : '表格全屏'"
        @click="toggleTableFullscreen"
      />
      <n-card class="data-card">
        <n-data-table
          v-model:checked-row-keys="checkedRowKeys"
          :bordered="false"
          :columns="columns"
          :data="items"
          :loading="loading"
          :row-props="rowProps"
          :row-key="(r: PurchaseMaterial) => r.id"
          :scroll-x="tableScrollX"
        />
        <div class="pagination-bar">
          <n-pagination
            v-model:page="page"
            v-model:page-size="pageSize"
            :item-count="total"
            :page-sizes="[10, 20, 50, 100, 200]"
            show-size-picker
            @update:page="changePage"
            @update:page-size="changePageSize"
          />
        </div>
      </n-card>
    </div>
    <n-modal
      v-model:show="showBatchEdit"
      preset="card"
      title="批量修改申购计划"
      style="width: 620px"
      :mask-closable="false"
    >
      <n-alert type="info" style="margin-bottom: 16px">
        已选择 {{ selectedPlans.length }} 条计划。仅勾选的字段会被统一修改。
      </n-alert>
      <n-form label-placement="top">
        <div class="form-grid">
          <n-form-item>
            <template #label>
              <n-checkbox v-model:checked="batchEditForm.update_plan_date">修改需求日期</n-checkbox>
            </template>
            <n-date-picker
              v-model:value="batchEditForm.plan_date"
              type="date"
              class="full-width"
              :disabled="!batchEditForm.update_plan_date"
            />
          </n-form-item>
          <n-form-item>
            <template #label>
              <n-checkbox v-model:checked="batchEditForm.update_actual_demand_person">
                修改实际需求人
              </n-checkbox>
            </template>
            <n-input
              v-model:value="batchEditForm.actual_demand_person"
              maxlength="128"
              :disabled="!batchEditForm.update_actual_demand_person"
            />
          </n-form-item>
          <n-form-item>
            <template #label>
              <n-checkbox v-model:checked="batchEditForm.update_subitem_no">修改子项号</n-checkbox>
            </template>
            <n-input
              v-model:value="batchEditForm.subitem_no"
              maxlength="64"
              placeholder="留空将清除子项号"
              :disabled="!batchEditForm.update_subitem_no"
            />
          </n-form-item>
          <n-form-item>
            <template #label>
              <n-checkbox v-model:checked="batchEditForm.update_status">修改状态</n-checkbox>
            </template>
            <n-select
              v-model:value="batchEditForm.status"
              :options="purchasePlanStatusOptions"
              :disabled="!batchEditForm.update_status"
            />
          </n-form-item>
        </div>
        <n-form-item>
          <template #label>
            <n-checkbox v-model:checked="batchEditForm.update_usage">修改用途</n-checkbox>
          </template>
          <n-input
            v-model:value="batchEditForm.usage"
            type="textarea"
            maxlength="500"
            show-count
            :disabled="!batchEditForm.update_usage"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showBatchEdit = false">取消</n-button>
          <n-button type="primary" :loading="batchUpdating" @click="batchUpdate">
            保存修改
          </n-button>
        </n-space>
      </template>
    </n-modal>
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
    >
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <div class="form-grid">
          <n-form-item label="物料编码（已有时填写）">
            <n-input
              v-model:value="form.material_code"
              maxlength="64"
              placeholder="没有编码可留空"
            />
          </n-form-item>
          <n-form-item label="需求日期" required>
            <n-date-picker v-model:value="createPlanDate" type="date" class="full-width" />
          </n-form-item>
          <n-form-item label="状态" required>
            <n-select v-model:value="form.status" :options="purchasePlanStatusOptions" />
          </n-form-item>
          <n-form-item label="名称" path="name">
            <n-input v-model:value="form.name" maxlength="128" />
          </n-form-item>
          <n-form-item label="型号规格" path="model_spec">
            <n-input v-model:value="form.model_spec" maxlength="255" />
          </n-form-item>
          <n-form-item label="计划数量" path="planned_qty">
            <QuantityInput v-model:value="form.planned_qty" :decimal-places="1" />
          </n-form-item>
          <n-form-item label="计量单位" path="unit_id">
            <n-select v-model:value="form.unit_id" :options="dictionaries.unitOptions" />
          </n-form-item>
          <n-form-item label="实际需求人" path="actual_demand_person">
            <n-input
              v-model:value="form.actual_demand_person"
              maxlength="128"
              placeholder="填写提出实际需求的员工"
            />
          </n-form-item>
          <n-form-item label="申购负责人" path="purchase_responsible">
            <n-input v-model:value="form.purchase_responsible" maxlength="128" />
          </n-form-item>
          <n-form-item label="子项号">
            <n-input v-model:value="form.subitem_no" maxlength="64" placeholder="选填" />
          </n-form-item>
          <n-form-item label="用途" path="usage">
            <n-input v-model:value="form.usage" maxlength="500" />
          </n-form-item>
        </div>
        <n-form-item label="关联二级库物资"
          ><MaterialSelector
            :value="form.stock_material_id ?? null"
            @update:value="form.stock_material_id = $event ?? undefined"
        /></n-form-item>
        <n-form-item label="备注"
          ><n-input
            v-model:value="form.remark"
            type="textarea"
            maxlength="1000"
            show-count /></n-form-item
        ><n-form-item label="图片附件"
          ><ImageUploader v-model:files="images" /></n-form-item></n-form
      ><template #footer
        ><n-space justify="end"
          ><n-button @click="show = false">取消</n-button
          ><n-button type="primary" :loading="saving" @click="save">保存</n-button></n-space
        ></template
      ></n-modal
    >
  </div>
</template>

<style scoped>
.filter-heading,
.filter-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.filter-heading {
  margin-bottom: 18px;
}

.purchase-plan-filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.filter-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 7px;
}

.filter-field > span {
  color: #4b5565;
  font-size: 13px;
  font-weight: 500;
}

.filter-field :deep(.n-input),
.filter-field :deep(.n-select) {
  width: 100%;
}

.filter-field :deep(.n-input) {
  background-color: rgb(255 255 255 / 88%);
}

.filter-actions {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #edf1f6;
}

.filter-action-buttons {
  display: flex;
  flex: none;
  gap: 10px;
}

.filter-action-buttons :deep(.n-button) {
  min-width: 88px;
}

.purchase-plan-table-area {
  position: relative;
}

.table-fullscreen-toggle {
  position: absolute;
  z-index: 2;
  top: 6px;
  right: 6px;
  width: 28px;
  height: 28px;
  color: #aeb7c4;
}

.table-fullscreen-toggle::before {
  width: 13px;
  height: 13px;
  border-top: 2px solid currentcolor;
  border-right: 2px solid currentcolor;
  border-top-right-radius: 1px;
  content: '';
  transition:
    color 0.18s ease,
    transform 0.18s ease;
}

.table-fullscreen-toggle.is-fullscreen::before {
  transform: rotate(180deg);
}

.table-fullscreen-toggle:hover {
  background: rgb(148 163 184 / 10%);
  color: #8e99a8;
}

.model-spec-clamp {
  display: -webkit-box;
  max-height: 3em;
  overflow: hidden;
  line-height: 1.5;
  overflow-wrap: anywhere;
  word-break: break-all;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.purchase-plan-table-area:fullscreen {
  overflow: auto;
  padding: 16px;
  background: var(--color-bg);
}

.purchase-plan-table-area:fullscreen :deep(.n-card) {
  min-height: 100%;
}

@media (max-width: 1600px) {
  .purchase-plan-filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1220px) {
  .purchase-plan-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .purchase-plan-filter-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .filter-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .filter-action-buttons {
    justify-content: flex-end;
  }
}
</style>
