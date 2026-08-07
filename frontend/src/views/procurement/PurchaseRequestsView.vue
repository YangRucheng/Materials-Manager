<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NTag, useMessage, type DataTableBaseColumn, type DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import type {
  FileObject,
  PurchaseRecord,
  PurchaseRecordBatchUpdate,
  PurchaseRecordFilterOptions,
  PurchaseRecordWrite,
} from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { aiSearchApi } from '@/api/aiSearch'
import ColumnVisibilityPicker from '@/components/ColumnVisibilityPicker.vue'
import ExportButton from '@/components/ExportButton.vue'
import ImageUploader from '@/components/ImageUploader.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import type { ExportOption } from '@/types/export'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'
import { dateToTimestamp, formatDate, toShanghaiDate } from '@/utils/time'
import { downloadBlob } from '@/utils/download'
import { routeQueryString } from '@/utils/routeQuery'
import { useImplicitAiSearch } from '@/composables/useImplicitAiSearch'
import { usePagedTable } from '@/composables/usePagedTable'
import { useShiftWheelHorizontalScroll } from '@/composables/useShiftWheelHorizontalScroll'
import { renderTwoLineText } from '@/utils/tableText'
import { useAuthStore } from '@/stores/auth'
import { purchaseCategoryOptions } from '@/constants/purchase'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const rowClickGuard = createTableRowClickGuard()
const EMPTY_STATUS_FILTER = '__empty_status__'
type RecordFilters = {
  name: string
  model_spec: string
  trace_no: string
  purchase_order_no: string
  actual_demand_person: string | null
  purchase_responsible: string | null
  salesperson: string | null
  status: string | null
}
const {
  items,
  total,
  page,
  pageSize,
  loading,
  filters,
  load,
  query,
  changePage,
  changePageSize,
  resetFilters,
  syncRoute,
} = usePagedTable<PurchaseRecord, RecordFilters>({
  fetch: (f, pager) =>
    procurementApi.records({
      page: pager.page,
      page_size: pager.page_size,
      name: searchName.value,
      model_spec: f.model_spec.trim() || undefined,
      trace_no: f.trace_no.trim() || undefined,
      purchase_order_no: f.purchase_order_no.trim() || undefined,
      actual_demand_person: f.actual_demand_person?.trim() || undefined,
      purchase_responsible: f.purchase_responsible?.trim() || undefined,
      salesperson: f.salesperson?.trim() || undefined,
      status: f.status && f.status !== EMPTY_STATUS_FILTER ? f.status : undefined,
      empty_status: f.status === EMPTY_STATUS_FILTER || undefined,
    }),
  initialFilters: () => ({
    name: '',
    model_spec: '',
    trace_no: '',
    purchase_order_no: '',
    actual_demand_person: null,
    purchase_responsible: null,
    salesperson: null,
    status: null,
  }),
  onLoaded: () => {
    checkedRowKeys.value = []
  },
  beforeQuery: () => clearExpandedName(),
  urlSync: {
    routeName: 'purchase-records',
    fromQuery: (route) => ({
      name: routeQueryString(route.query.name),
      model_spec: routeQueryString(route.query.model_spec),
      trace_no: routeQueryString(route.query.trace_no),
      purchase_order_no: routeQueryString(route.query.purchase_order_no),
      actual_demand_person: routeQueryString(route.query.actual_demand_person) || null,
      purchase_responsible: routeQueryString(route.query.purchase_responsible) || null,
      salesperson: routeQueryString(route.query.salesperson) || null,
      status: routeQueryString(route.query.status) || null,
    }),
    toQuery: (f) => ({
      name: f.name,
      model_spec: f.model_spec,
      trace_no: f.trace_no,
      purchase_order_no: f.purchase_order_no,
      actual_demand_person: f.actual_demand_person || undefined,
      purchase_responsible: f.purchase_responsible || undefined,
      salesperson: f.salesperson || undefined,
      status: f.status || undefined,
    }),
  },
})
const { searchName, applyExpandedName, clearExpandedName } = useImplicitAiSearch(() => filters.name)
const aiAvailable = ref(false)
const aiSearching = ref(false)
const resultExporting = ref(false)
const batchUpdating = ref(false)
const showBatchEdit = ref(false)
const checkedRowKeys = ref<Array<string | number>>([])
const tableAreaRef = ref<HTMLElement | null>(null)
const exportOptions: ExportOption[] = [{ label: '导出查询结果', key: 'results' }]
// 单条编辑弹窗（点击行打开，与申购计划一致）
const showEdit = ref(false)
const editing = ref<PurchaseRecord | null>(null)
const editSaving = ref(false)
const editAdvancedSections = ref<string[]>([])
const editPlanDate = ref<number | null>(null)
const editPurchaseDate = ref<number | null>(null)
const editConsolidationDate = ref<number | null>(null)
const editSailingDate = ref<number | null>(null)
const editImages = ref<FileObject[]>([])
const editForm = reactive<PurchaseRecordWrite>({
  plan_date: '',
  material_code: '',
  category: '',
  demand_department: '',
  material_name: '',
  model_spec: '',
  unit_name: '',
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
const filterOptions = ref<PurchaseRecordFilterOptions>({
  actual_demand_persons: [],
  purchase_responsibles: [],
  subitem_nos: [],
  categories: [],
  salespersons: [],
  statuses: [],
})
const actualDemandPersonOptions = computed(() =>
  filterOptions.value.actual_demand_persons.map((value) => ({ label: value, value })),
)
const purchaseResponsibleOptions = computed(() =>
  filterOptions.value.purchase_responsibles.map((value) => ({ label: value, value })),
)
const salespersonOptions = computed(() =>
  filterOptions.value.salespersons.map((value) => ({ label: value, value })),
)
const statusOptions = computed(() => [
  { label: '空状态', value: EMPTY_STATUS_FILTER },
  ...filterOptions.value.statuses.map((value) => ({ label: value, value })),
])
const selectedRecords = computed(() => {
  const selected = new Set(checkedRowKeys.value.map(Number))
  return items.value.filter((item) => selected.has(item.line_id))
})
const batchEditForm = reactive({
  update_plan_date: false,
  plan_date: null as number | null,
  update_purchase_order_no: false,
  purchase_order_no: '',
  update_trace_no: false,
  trace_no: '',
  update_contract_no: false,
  contract_no: '',
  update_vessel_no: false,
  vessel_no: '',
  update_consolidation_date: false,
  consolidation_date: null as number | null,
  update_consolidation_port: false,
  consolidation_port: '',
  update_sailing_date: false,
  sailing_date: null as number | null,
  update_purchase_date: false,
  purchase_date: null as number | null,
  update_actual_demand_person: false,
  actual_demand_person: '',
  update_purchase_responsible: false,
  purchase_responsible: '',
  update_salesperson: false,
  salesperson: '',
  update_status: false,
  status: '',
  update_record_remark: false,
  record_remark: '',
})
const activeFilterCount = computed(
  () => Object.values(filters).filter((value) => value?.trim()).length,
)
type RecordColumnKey =
  | 'plan_date'
  | 'purchase_order_no'
  | 'trace_no'
  | 'contract_no'
  | 'vessel_no'
  | 'consolidation_date'
  | 'consolidation_port'
  | 'sailing_date'
  | 'category'
  | 'demand_department'
  | 'material_name'
  | 'purchase_qty'
  | 'usage'
  | 'actual_demand_person'
  | 'purchase_responsible'
  | 'salesperson'
  | 'status'
  | 'purchase_date'

const availableColumns: Array<{
  key: RecordColumnKey
  label: string
  column: DataTableBaseColumn<PurchaseRecord>
}> = [
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
    key: 'purchase_date',
    label: '申购日期',
    column: {
      title: '申购日期',
      key: 'purchase_date',
      width: tableColumnWidths.date,
      render: (row) => (row.purchase_date ? formatDate(row.purchase_date) : '\\'),
    },
  },
  {
    key: 'purchase_order_no',
    label: '申购单号',
    column: {
      title: '申购单号',
      key: 'purchase_order_no',
      width: tableColumnWidths.identifier,
      render: (row) => renderTwoLineText(row.purchase_order_no),
    },
  },
  {
    key: 'trace_no',
    label: '追溯号',
    column: {
      title: '追溯号',
      key: 'trace_no',
      width: tableColumnWidths.identifier,
      render: (row) => renderTwoLineText(row.trace_no),
    },
  },
  {
    key: 'contract_no',
    label: '合同号',
    column: {
      title: '合同号',
      key: 'contract_no',
      width: tableColumnWidths.identifier,
      render: (row) => renderTwoLineText(row.contract_no),
    },
  },
  {
    key: 'vessel_no',
    label: '船号',
    column: {
      title: '船号',
      key: 'vessel_no',
      width: tableColumnWidths.identifier,
      render: (row) => renderTwoLineText(row.vessel_no),
    },
  },
  {
    key: 'consolidation_date',
    label: '集港日期',
    column: {
      title: '集港日期',
      key: 'consolidation_date',
      width: tableColumnWidths.date,
      render: (row) => (row.consolidation_date ? formatDate(row.consolidation_date) : '\\'),
    },
  },
  {
    key: 'consolidation_port',
    label: '集港港口',
    column: {
      title: '集港港口',
      key: 'consolidation_port',
      width: tableColumnWidths.identifier,
      render: (row) => renderTwoLineText(row.consolidation_port),
    },
  },
  {
    key: 'sailing_date',
    label: '发船日期',
    column: {
      title: '发船日期',
      key: 'sailing_date',
      width: tableColumnWidths.date,
      render: (row) => (row.sailing_date ? formatDate(row.sailing_date) : '\\'),
    },
  },
  {
    key: 'category',
    label: '类别',
    column: {
      title: '类别',
      key: 'category',
      width: tableColumnWidths.person,
      render: (row) => renderTwoLineText(row.category),
    },
  },
  {
    key: 'demand_department',
    label: '需求部门',
    column: {
      title: '需求部门',
      key: 'demand_department',
      width: tableColumnWidths.person,
      render: (row) => renderTwoLineText(row.demand_department),
    },
  },
  {
    key: 'material_name',
    label: '物资',
    column: {
      title: '物资',
      key: 'material_name',
      width: tableColumnWidths.material,
      render: (row) =>
        h(
          'div',
          {
            class: 'table-material-summary',
            title: `${row.material_name}\n${row.material_code || '\\'}｜${row.model_spec}`,
          },
          [
            h('div', { class: 'table-material-summary__name' }, row.material_name),
            h(
              'div',
              { class: 'table-material-summary__meta' },
              `${row.material_code || '\\'}｜${row.model_spec}`,
            ),
          ],
        ),
    },
  },
  {
    key: 'purchase_qty',
    label: '申购数量',
    column: {
      title: '申购数量',
      key: 'purchase_qty',
      width: tableColumnWidths.quantity,
      render: (row) => renderTwoLineText(`${row.purchase_qty} ${row.unit_name}`),
    },
  },
  {
    key: 'usage',
    label: '用途',
    column: {
      title: '用途',
      key: 'usage',
      width: tableColumnWidths.text,
      render: (row) => renderTwoLineText(row.usage),
    },
  },
  {
    key: 'actual_demand_person',
    label: '实际需求人',
    column: {
      title: '实际需求人',
      key: 'actual_demand_person',
      width: tableColumnWidths.person,
      render: (row) => renderTwoLineText(row.actual_demand_person),
    },
  },
  {
    key: 'purchase_responsible',
    label: '申购负责人',
    column: {
      title: '申购负责人',
      key: 'purchase_responsible',
      width: tableColumnWidths.person,
      render: (row) => renderTwoLineText(row.purchase_responsible),
    },
  },
  {
    key: 'salesperson',
    label: '业务员',
    column: {
      title: '业务员',
      key: 'salesperson',
      width: tableColumnWidths.person,
      render: (row) => renderTwoLineText(row.salesperson),
    },
  },
  {
    key: 'status',
    label: '状态',
    column: {
      title: '状态',
      key: 'status',
      width: tableColumnWidths.status,
      render: (row) => h(NTag, null, { default: () => row.status || '\\' }),
    },
  },
]
const optionalShippingColumnKeys = new Set<RecordColumnKey>([
  'contract_no',
  'vessel_no',
  'consolidation_date',
  'consolidation_port',
  'sailing_date',
])
const visibleColumnKeys = ref<RecordColumnKey[]>(
  availableColumns
    .filter((item) => !optionalShippingColumnKeys.has(item.key))
    .map((item) => item.key),
)
const fieldOptions = availableColumns.map((item) => ({ label: item.label, value: item.key }))
const columns = computed<DataTableColumns<PurchaseRecord>>(() =>
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
useShiftWheelHorizontalScroll(tableAreaRef)
function setVisibleColumnKeys(value: string[]) {
  visibleColumnKeys.value = value as RecordColumnKey[]
}
function rowProps(row: PurchaseRecord) {
  return {
    style: 'cursor: pointer',
    onMousedown: rowClickGuard.onMouseDown,
    onClick: (event: MouseEvent) => {
      if (rowClickGuard.shouldIgnore(event)) return
      // 点击行直接打开编辑弹窗（与申购计划一致）
      openEditRecord(row)
    },
  }
}

async function loadFilterOptions() {
  filterOptions.value = await procurementApi.recordFilterOptions()
}

async function loadAiStatus() {
  try {
    aiAvailable.value = (await aiSearchApi.status()).available
  } catch {
    aiAvailable.value = false
  }
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
    // 走原语而非 query()，避免 beforeQuery 清掉刚 apply 的扩展名
    page.value = 1
    await syncRoute()
    await load()
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
    const content = await procurementApi.exportRecordResults({
      columns: exportColumns,
      name: searchName.value,
      model_spec: filters.model_spec.trim() || undefined,
      trace_no: filters.trace_no.trim() || undefined,
      purchase_order_no: filters.purchase_order_no.trim() || undefined,
      actual_demand_person: filters.actual_demand_person?.trim() || undefined,
      purchase_responsible: filters.purchase_responsible?.trim() || undefined,
      salesperson: filters.salesperson?.trim() || undefined,
      status: filters.status && filters.status !== EMPTY_STATUS_FILTER ? filters.status : undefined,
      empty_status: filters.status === EMPTY_STATUS_FILTER,
    })
    const date = toShanghaiDate(Date.now()).replace(/-/g, '')
    downloadBlob(content, `申购记录导出_${date}.xlsx`)
    message.success('查询结果已导出')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    resultExporting.value = false
  }
}

function handleExport(key: string) {
  if (key === 'results') void exportResults()
}

function syncEditForm(value: PurchaseRecord) {
  Object.assign(editForm, {
    plan_date: value.plan_date,
    material_code: value.material_code || '',
    category: value.category || '',
    demand_department: value.demand_department,
    material_name: value.material_name,
    model_spec: value.model_spec,
    unit_name: value.unit_name,
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
  editPlanDate.value = dateToTimestamp(value.plan_date)
  editPurchaseDate.value = dateToTimestamp(value.purchase_date)
  editConsolidationDate.value = dateToTimestamp(value.consolidation_date)
  editSailingDate.value = dateToTimestamp(value.sailing_date)
  editImages.value = [...value.images]
}

function openEditRecord(row: PurchaseRecord) {
  editing.value = row
  syncEditForm(row)
  editAdvancedSections.value = []
  showEdit.value = true
}

function openRecordInNewPage() {
  const target = editing.value
  if (!target) return
  showEdit.value = false
  editing.value = null
  void router.push(`/procurement/records/${target.line_id}`)
}

async function saveEditRecord() {
  if (
    !editing.value ||
    !editPlanDate.value ||
    !editPurchaseDate.value ||
    !editForm.material_name.trim() ||
    !editForm.model_spec.trim() ||
    !editForm.unit_name.trim() ||
    !editForm.actual_demand_person.trim() ||
    !editForm.purchase_responsible.trim() ||
    !editForm.purchase_qty ||
    !editForm.usage.trim() ||
    !editForm.status.trim()
  ) {
    message.error('请完整填写日期、物资、申购数量、用途、人员和状态')
    return
  }
  editSaving.value = true
  try {
    await procurementApi.updateRecord(editing.value.line_id, {
      ...editForm,
      plan_date: toShanghaiDate(editPlanDate.value),
      purchase_date: toShanghaiDate(editPurchaseDate.value),
      consolidation_date: editConsolidationDate.value
        ? toShanghaiDate(editConsolidationDate.value)
        : undefined,
      sailing_date: editSailingDate.value ? toShanghaiDate(editSailingDate.value) : undefined,
      material_code: editForm.material_code?.trim() || undefined,
      category: editForm.category?.trim() || undefined,
      subitem_no: editForm.subitem_no?.trim() || undefined,
      plan_remark: editForm.plan_remark?.trim() || undefined,
      record_remark: editForm.record_remark?.trim() || undefined,
      purchase_order_no: editForm.purchase_order_no?.trim() || null,
      trace_no: editForm.trace_no?.trim() || null,
      contract_no: editForm.contract_no?.trim() || null,
      vessel_no: editForm.vessel_no?.trim() || null,
      consolidation_port: editForm.consolidation_port?.trim() || null,
      salesperson: editForm.salesperson?.trim() || undefined,
      image_ids: editImages.value.map((image) => image.id),
    })
    message.success('申购记录已保存')
    showEdit.value = false
    editing.value = null
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    editSaving.value = false
  }
}

function openBatchEdit() {
  if (!selectedRecords.value.length) {
    message.warning('请先选择至少一条申购记录')
    return
  }
  Object.assign(batchEditForm, {
    update_plan_date: false,
    plan_date: null,
    update_purchase_order_no: false,
    purchase_order_no: '',
    update_trace_no: false,
    trace_no: '',
    update_contract_no: false,
    contract_no: '',
    update_vessel_no: false,
    vessel_no: '',
    update_consolidation_date: false,
    consolidation_date: null,
    update_consolidation_port: false,
    consolidation_port: '',
    update_sailing_date: false,
    sailing_date: null,
    update_purchase_date: false,
    purchase_date: null,
    update_actual_demand_person: false,
    actual_demand_person: '',
    update_purchase_responsible: false,
    purchase_responsible: '',
    update_salesperson: false,
    salesperson: '',
    update_status: false,
    status: '',
    update_record_remark: false,
    record_remark: '',
  })
  showBatchEdit.value = true
}

async function batchUpdate() {
  const payload: PurchaseRecordBatchUpdate = {
    records: selectedRecords.value.map((item) => ({
      line_id: item.line_id,
      version: item.version,
    })),
  }
  if (batchEditForm.update_plan_date) {
    if (!batchEditForm.plan_date) {
      message.error('请选择需求日期')
      return
    }
    payload.plan_date = toShanghaiDate(batchEditForm.plan_date)
  }
  if (batchEditForm.update_purchase_order_no) {
    payload.purchase_order_no = batchEditForm.purchase_order_no.trim() || null
  }
  if (batchEditForm.update_trace_no) {
    payload.trace_no = batchEditForm.trace_no.trim() || null
  }
  if (batchEditForm.update_contract_no) {
    payload.contract_no = batchEditForm.contract_no.trim() || null
  }
  if (batchEditForm.update_vessel_no) {
    payload.vessel_no = batchEditForm.vessel_no.trim() || null
  }
  if (batchEditForm.update_consolidation_date) {
    payload.consolidation_date = batchEditForm.consolidation_date
      ? toShanghaiDate(batchEditForm.consolidation_date)
      : null
  }
  if (batchEditForm.update_consolidation_port) {
    payload.consolidation_port = batchEditForm.consolidation_port.trim() || null
  }
  if (batchEditForm.update_sailing_date) {
    payload.sailing_date = batchEditForm.sailing_date
      ? toShanghaiDate(batchEditForm.sailing_date)
      : null
  }
  if (batchEditForm.update_purchase_date) {
    payload.purchase_date = batchEditForm.purchase_date
      ? toShanghaiDate(batchEditForm.purchase_date)
      : null
  }
  if (batchEditForm.update_actual_demand_person) {
    const value = batchEditForm.actual_demand_person.trim()
    if (!value) {
      message.error('请选择或输入实际需求人')
      return
    }
    payload.actual_demand_person = value
  }
  if (batchEditForm.update_purchase_responsible) {
    const value = batchEditForm.purchase_responsible.trim()
    if (!value) {
      message.error('请选择或输入申购负责人')
      return
    }
    payload.purchase_responsible = value
  }
  if (batchEditForm.update_salesperson) {
    payload.salesperson = batchEditForm.salesperson.trim() || null
  }
  if (batchEditForm.update_status) {
    const value = batchEditForm.status.trim()
    if (!value) {
      message.error('请输入申购状态')
      return
    }
    payload.status = value
  }
  if (batchEditForm.update_record_remark) {
    payload.record_remark = batchEditForm.record_remark.trim() || null
  }
  if (Object.keys(payload).length === 1) {
    message.warning('请至少勾选一个需要修改的字段')
    return
  }

  const updatedCount = selectedRecords.value.length
  batchUpdating.value = true
  try {
    await procurementApi.batchUpdateRecords(payload)
    message.success(`已批量修改 ${updatedCount} 条申购记录`)
    showBatchEdit.value = false
    checkedRowKeys.value = []
    await Promise.all([load(), loadFilterOptions()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '批量修改失败')
  } finally {
    batchUpdating.value = false
  }
}

onMounted(() => {
  void loadFilterOptions()
  void loadAiStatus()
  // 列表首载由 usePagedTable（immediate）触发
})
</script>

<template>
  <div class="page purchase-records-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">申购记录</h1>
      </div>
      <n-space align="center">
        <n-button
          v-if="auth.can('purchase:write')"
          :disabled="!selectedRecords.length"
          @click="openBatchEdit"
        >
          批量修改（{{ selectedRecords.length }}）
        </n-button>
        <n-tag :bordered="false" round type="info">共 {{ total }} 条记录</n-tag>
        <ExportButton :options="exportOptions" :loading="resultExporting" @select="handleExport" />
      </n-space>
    </div>
    <n-card class="filter-card" :bordered="false">
      <div class="filter-heading">
        <div class="filter-title">筛选条件</div>
        <n-tag v-if="activeFilterCount" :bordered="false" round type="success">
          已启用 {{ activeFilterCount }} 项
        </n-tag>
      </div>
      <div class="purchase-records-filter-grid">
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
          <span>追溯号</span>
          <n-input
            v-model:value="filters.trace_no"
            placeholder="输入追溯号"
            clearable
            @keyup.enter="query"
          />
        </label>
        <label class="filter-field">
          <span>申购单号</span>
          <n-input
            v-model:value="filters.purchase_order_no"
            placeholder="输入申购单号"
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
          <span>申购负责人</span>
          <n-select
            v-model:value="filters.purchase_responsible"
            :options="purchaseResponsibleOptions"
            placeholder="选择或搜索负责人"
            filterable
            clearable
          />
        </label>
        <label class="filter-field">
          <span>业务员</span>
          <n-select
            v-model:value="filters.salesperson"
            :options="salespersonOptions"
            placeholder="选择或搜索业务员"
            filterable
            clearable
          />
        </label>
        <label class="filter-field">
          <span>申购状态</span>
          <n-select
            v-model:value="filters.status"
            :options="statusOptions"
            clearable
            filterable
            placeholder="选择或搜索状态"
          />
        </label>
      </div>
      <div class="filter-actions">
        <ColumnVisibilityPicker
          :value="visibleColumnKeys"
          :options="fieldOptions"
          storage-key="procurement.purchase-records.visible-columns.v2"
          @update:value="setVisibleColumnKeys"
        />
        <div class="filter-action-buttons">
          <n-button @click="resetFilters">重置</n-button>
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
    <div ref="tableAreaRef">
      <n-card class="records-card data-card" :bordered="false">
        <n-data-table
          v-model:checked-row-keys="checkedRowKeys"
          :bordered="false"
          :columns="columns"
          :data="items"
          :loading="loading"
          :row-props="rowProps"
          :row-key="(row: PurchaseRecord) => row.line_id"
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
      draggable
      title="批量修改申购记录"
      style="width: 760px; max-width: calc(100vw - 32px)"
      :mask-closable="false"
    >
      <n-alert type="info" style="margin-bottom: 16px">
        已选择 {{ selectedRecords.length }}
        条记录。仅勾选的字段会被统一修改；单据共享字段会同步影响同一申购单下的其他物资。
      </n-alert>
      <n-scrollbar style="max-height: 65vh" content-style="padding-right: 12px">
        <n-form label-placement="top">
          <div class="form-grid batch-edit-grid">
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_plan_date">
                  修改需求日期
                </n-checkbox>
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
                <n-checkbox v-model:checked="batchEditForm.update_purchase_order_no">
                  修改申购单号
                </n-checkbox>
              </template>
              <n-input
                v-model:value="batchEditForm.purchase_order_no"
                maxlength="128"
                placeholder="留空将清除申购单号"
                :disabled="!batchEditForm.update_purchase_order_no"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_trace_no">修改追溯号</n-checkbox>
              </template>
              <n-input
                v-model:value="batchEditForm.trace_no"
                maxlength="128"
                placeholder="留空将清除追溯号"
                :disabled="!batchEditForm.update_trace_no"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_contract_no"
                  >修改合同号</n-checkbox
                >
              </template>
              <n-input
                v-model:value="batchEditForm.contract_no"
                maxlength="128"
                placeholder="留空将清除合同号"
                :disabled="!batchEditForm.update_contract_no"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_vessel_no">修改船号</n-checkbox>
              </template>
              <n-input
                v-model:value="batchEditForm.vessel_no"
                maxlength="128"
                placeholder="留空将清除船号"
                :disabled="!batchEditForm.update_vessel_no"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_consolidation_date">
                  修改集港日期
                </n-checkbox>
              </template>
              <n-date-picker
                v-model:value="batchEditForm.consolidation_date"
                type="date"
                class="full-width"
                clearable
                :disabled="!batchEditForm.update_consolidation_date"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_consolidation_port">
                  修改集港港口
                </n-checkbox>
              </template>
              <n-input
                v-model:value="batchEditForm.consolidation_port"
                maxlength="128"
                placeholder="留空将清除集港港口"
                :disabled="!batchEditForm.update_consolidation_port"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_sailing_date">
                  修改发船日期
                </n-checkbox>
              </template>
              <n-date-picker
                v-model:value="batchEditForm.sailing_date"
                type="date"
                class="full-width"
                clearable
                :disabled="!batchEditForm.update_sailing_date"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_purchase_date">
                  修改申购日期
                </n-checkbox>
              </template>
              <n-date-picker
                v-model:value="batchEditForm.purchase_date"
                type="date"
                class="full-width"
                clearable
                :disabled="!batchEditForm.update_purchase_date"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_actual_demand_person">
                  修改实际需求人
                </n-checkbox>
              </template>
              <n-select
                v-model:value="batchEditForm.actual_demand_person"
                :options="actualDemandPersonOptions"
                filterable
                tag
                placeholder="选择或输入实际需求人"
                :disabled="!batchEditForm.update_actual_demand_person"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_purchase_responsible">
                  修改申购负责人
                </n-checkbox>
              </template>
              <n-select
                v-model:value="batchEditForm.purchase_responsible"
                :options="purchaseResponsibleOptions"
                filterable
                tag
                placeholder="选择或输入申购负责人"
                :disabled="!batchEditForm.update_purchase_responsible"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_salesperson"
                  >修改业务员</n-checkbox
                >
              </template>
              <n-select
                v-model:value="batchEditForm.salesperson"
                :options="salespersonOptions"
                filterable
                tag
                clearable
                placeholder="留空将清除业务员"
                :disabled="!batchEditForm.update_salesperson"
              />
            </n-form-item>
            <n-form-item>
              <template #label>
                <n-checkbox v-model:checked="batchEditForm.update_status">修改申购状态</n-checkbox>
              </template>
              <n-input
                v-model:value="batchEditForm.status"
                maxlength="128"
                placeholder="输入申购状态"
                :disabled="!batchEditForm.update_status"
              />
            </n-form-item>
          </div>
          <n-form-item>
            <template #label>
              <n-checkbox v-model:checked="batchEditForm.update_record_remark">
                修改申购记录备注
              </n-checkbox>
            </template>
            <n-input
              v-model:value="batchEditForm.record_remark"
              type="textarea"
              maxlength="1000"
              show-count
              placeholder="留空将清除申购记录备注"
              :disabled="!batchEditForm.update_record_remark"
            />
          </n-form-item>
        </n-form>
      </n-scrollbar>
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
      v-model:show="showEdit"
      preset="card"
      draggable
      :title="editing ? '编辑申购记录' : '申购记录'"
      style="width: 760px; max-width: calc(100vw - 32px)"
      :mask-closable="false"
    >
      <n-scrollbar style="max-height: 70vh" content-style="padding-right: 12px">
        <n-form label-placement="top">
          <div class="form-grid">
            <n-form-item label="需求日期" required>
              <n-date-picker v-model:value="editPlanDate" type="date" class="full-width" />
            </n-form-item>
            <n-form-item label="申购日期" required>
              <n-date-picker v-model:value="editPurchaseDate" type="date" class="full-width" />
            </n-form-item>
            <n-form-item label="申购单号">
              <n-input
                v-model:value="editForm.purchase_order_no"
                maxlength="128"
                placeholder="可留空"
              />
            </n-form-item>
            <n-form-item label="追溯号">
              <n-input v-model:value="editForm.trace_no" maxlength="128" placeholder="可留空" />
            </n-form-item>
            <n-form-item label="类别">
              <n-select
                v-model:value="editForm.category"
                :options="purchaseCategoryOptions"
                filterable
                clearable
                placeholder="选择类别"
              />
            </n-form-item>
            <n-form-item label="状态" required>
              <n-input
                v-model:value="editForm.status"
                maxlength="128"
                placeholder="可填写任意状态"
              />
            </n-form-item>
            <n-form-item label="名称" required>
              <n-input v-model:value="editForm.material_name" maxlength="128" />
            </n-form-item>
            <n-form-item label="型号规格" required>
              <n-input v-model:value="editForm.model_spec" maxlength="255" />
            </n-form-item>
            <n-form-item label="申购数量 / 计量单位" required>
              <n-input-group>
                <QuantityInput
                  v-model:value="editForm.purchase_qty"
                  :decimal-places="1"
                  class="quantity-input"
                />
                <n-input
                  v-model:value="editForm.unit_name"
                  maxlength="32"
                  placeholder="计量单位"
                  class="quantity-unit-select"
                />
              </n-input-group>
            </n-form-item>
            <n-form-item label="实际需求人" required>
              <n-input v-model:value="editForm.actual_demand_person" maxlength="128" />
            </n-form-item>
            <n-form-item label="申购负责人" required>
              <n-input v-model:value="editForm.purchase_responsible" maxlength="128" />
            </n-form-item>
            <n-form-item label="业务员">
              <n-input v-model:value="editForm.salesperson" maxlength="128" />
            </n-form-item>
            <n-form-item label="子项号">
              <n-input v-model:value="editForm.subitem_no" maxlength="64" placeholder="选填" />
            </n-form-item>
            <n-form-item label="用途" required>
              <n-input v-model:value="editForm.usage" maxlength="500" />
            </n-form-item>
          </div>
          <n-collapse v-model:expanded-names="editAdvancedSections" class="edit-advanced-fields">
            <n-collapse-item name="advanced">
              <template #header>
                <span class="advanced-header">更多设置</span>
              </template>
              <div class="form-grid">
                <n-form-item label="合同号">
                  <n-input
                    v-model:value="editForm.contract_no"
                    maxlength="128"
                    placeholder="可留空"
                  />
                </n-form-item>
                <n-form-item label="船号">
                  <n-input
                    v-model:value="editForm.vessel_no"
                    maxlength="128"
                    placeholder="可留空"
                  />
                </n-form-item>
                <n-form-item label="集港日期">
                  <n-date-picker
                    v-model:value="editConsolidationDate"
                    type="date"
                    class="full-width"
                    clearable
                  />
                </n-form-item>
                <n-form-item label="集港港口">
                  <n-input
                    v-model:value="editForm.consolidation_port"
                    maxlength="128"
                    placeholder="可留空"
                  />
                </n-form-item>
                <n-form-item label="发船日期">
                  <n-date-picker
                    v-model:value="editSailingDate"
                    type="date"
                    class="full-width"
                    clearable
                  />
                </n-form-item>
                <n-form-item label="物料编码">
                  <n-input
                    v-model:value="editForm.material_code"
                    maxlength="64"
                    placeholder="可留空"
                  />
                </n-form-item>
                <n-form-item label="需求部门" required>
                  <n-input v-model:value="editForm.demand_department" maxlength="128" />
                </n-form-item>
                <n-form-item label="关联二级库物资">
                  <MaterialSelector
                    :value="editForm.stock_material_id ?? null"
                    @update:value="editForm.stock_material_id = $event ?? undefined"
                  />
                </n-form-item>
              </div>
            </n-collapse-item>
          </n-collapse>
          <div class="form-grid">
            <n-form-item label="申购计划备注">
              <n-input
                v-model:value="editForm.plan_remark"
                type="textarea"
                maxlength="1000"
                show-count
              />
            </n-form-item>
            <n-form-item label="申购记录备注">
              <n-input
                v-model:value="editForm.record_remark"
                type="textarea"
                maxlength="1000"
                show-count
              />
            </n-form-item>
          </div>
          <n-form-item label="图片附件">
            <ImageUploader v-model:files="editImages" />
          </n-form-item>
        </n-form>
      </n-scrollbar>
      <template #footer>
        <n-space justify="space-between">
          <n-button
            v-if="editing"
            text
            type="primary"
            class="open-new-page-btn"
            @click="openRecordInNewPage"
            >在新页面查看</n-button
          >
          <span v-else></span>
          <n-space justify="end">
            <n-button @click="showEdit = false">取消</n-button>
            <n-button type="primary" :loading="editSaving" @click="saveEditRecord">保存</n-button>
          </n-space>
        </n-space>
      </template>
    </n-modal>
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

.purchase-records-filter-grid {
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

@media (max-width: 1600px) {
  .purchase-records-filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1220px) {
  .purchase-records-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .purchase-records-filter-grid {
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

.quantity-input {
  flex: 1;
}

.quantity-unit-select {
  width: 160px;
}

.edit-advanced-fields {
  margin-bottom: 18px;
  overflow: hidden;
  border-radius: 8px;
  background: #f6f8fb;
}

.edit-advanced-fields :deep(.n-collapse-item) {
  border-radius: 8px;
}

.edit-advanced-fields :deep(.n-collapse-item__header) {
  padding: 10px 12px;
  transition: background-color 0.2s ease;
}

.edit-advanced-fields :deep(.n-collapse-item__header:hover) {
  background: #eef2f9;
}

.edit-advanced-fields :deep(.n-collapse-item__content-inner) {
  padding: 4px 12px 14px;
}

.advanced-header {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  color: #4b5565;
}

.open-new-page-btn {
  align-self: center;
}
</style>
