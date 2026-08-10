<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  NTag,
  useDialog,
  useMessage,
  type DataTableBaseColumn,
  type DataTableColumns,
  type FormInst,
  type FormRules,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import type {
  FileObject,
  MaterialCodeLibrary,
  PurchaseFilterOptions,
  PurchaseMaterial,
  PurchaseMaterialBatchUpdate,
  PurchasePlanStatus,
  PurchaseMaterialWrite,
} from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { aiSearchApi } from '@/api/aiSearch'
import { useAuthStore } from '@/stores/auth'
import ImageUploader from '@/components/ImageUploader.vue'
import MaterialCodeSelector from '@/components/MaterialCodeSelector.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import PurchaseRecordHistoryDialog from '@/components/PurchaseRecordHistoryDialog.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import ColumnVisibilityPicker from '@/components/ColumnVisibilityPicker.vue'
import ExportButton from '@/components/ExportButton.vue'
import SortableHeader, { type SortOptionKey } from '@/components/SortableHeader.vue'
import type { ExportOption } from '@/types/export'
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
  defaultDemandDepartment,
  defaultPurchasePlanStatus,
  defaultPurchaseUrgency,
  purchaseCategoryOptions,
  purchaseUrgencyOptions,
  purchasePlanStatusOptions,
} from '@/constants/purchase'
import { dateToTimestamp, formatDate, toShanghaiDate } from '@/utils/time'
import { downloadBlob } from '@/utils/download'
import { routeQueryString } from '@/utils/routeQuery'
import { useImplicitAiSearch } from '@/composables/useImplicitAiSearch'
import { usePagedTable } from '@/composables/usePagedTable'
import { useShiftWheelHorizontalScroll } from '@/composables/useShiftWheelHorizontalScroll'
import { renderTwoLineText } from '@/utils/tableText'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const dialog = useDialog()
const rowClickGuard = createTableRowClickGuard()
const EMPTY_DEMAND_PERSON_FILTER = '__empty_actual_demand_person__'
const EMPTY_SUBITEM_FILTER = '__empty_subitem_no__'
const canViewArchivedPlans = computed(() => auth.user?.role === 'SUPER_ADMIN')
const statusFilterOptions = computed(() =>
  purchasePlanStatusOptions.filter(
    (option) => canViewArchivedPlans.value || option.value !== '已归档',
  ),
)
type PurchaseFilters = {
  name: string
  model_spec: string
  actual_demand_person: string | null
  subitem_no: string | null
  category: string | null
  status: PurchasePlanStatus[]
  sort_by: PlanColumnKey | null
  sort_order: 'asc' | 'desc' | null
}
// fromQuery 在 usePagedTable setup 期同步执行，早于 availableColumns 定义，
// 需在 hook 调用前声明运行时值用于校验 URL 恢复的 sort_by 合法性。
const PLAN_SORTABLE_KEYS: readonly PlanColumnKey[] = [
  'plan_no',
  'plan_date',
  'material_code',
  'category',
  'urgency',
  'demand_department',
  'name',
  'model_spec',
  'unit_name',
  'planned_qty',
  'actual_demand_person',
  'purchase_responsible',
  'subitem_no',
  'usage',
]
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
} = usePagedTable<PurchaseMaterial, PurchaseFilters>({
  fetch: (f, pager) =>
    procurementApi.materials({
      page: pager.page,
      page_size: pager.page_size,
      moved: false,
      name: searchName.value,
      model_spec: f.model_spec.trim() || undefined,
      actual_demand_person:
        f.actual_demand_person && f.actual_demand_person !== EMPTY_DEMAND_PERSON_FILTER
          ? f.actual_demand_person.trim()
          : undefined,
      empty_actual_demand_person:
        f.actual_demand_person === EMPTY_DEMAND_PERSON_FILTER || undefined,
      subitem_no: f.subitem_no && f.subitem_no !== EMPTY_SUBITEM_FILTER ? f.subitem_no : undefined,
      empty_subitem_no: f.subitem_no === EMPTY_SUBITEM_FILTER || undefined,
      category: f.category || undefined,
      status: f.status.length ? f.status : undefined,
      sort_by: f.sort_by || undefined,
      sort_order: f.sort_order || undefined,
    }),
  initialFilters: () => ({
    name: '',
    model_spec: '',
    actual_demand_person: null,
    subitem_no: null,
    category: null,
    status: [defaultPurchasePlanStatus],
    sort_by: null,
    sort_order: null,
  }),
  onLoaded: () => {
    checkedRowKeys.value = []
  },
  beforeQuery: () => clearExpandedName(),
  urlSync: {
    routeName: 'purchase-materials',
    fromQuery: (route) => {
      const routeStatuses = routeQueryString(route.query.status)
        .split(',')
        .filter((value): value is PurchasePlanStatus =>
          purchasePlanStatusOptions.some((option) => option.value === value),
        )
      const sortBy = routeQueryString(route.query.sort_by)
      const sortOrder = routeQueryString(route.query.sort_order)
      return {
        name: routeQueryString(route.query.name),
        model_spec: routeQueryString(route.query.model_spec),
        actual_demand_person: routeQueryString(route.query.actual_demand_person) || null,
        subitem_no: routeQueryString(route.query.subitem_no) || null,
        category: routeQueryString(route.query.category) || null,
        status:
          routeStatuses.filter((status) => canViewArchivedPlans.value || status !== '已归档')
            .length > 0
            ? routeStatuses.filter((status) => canViewArchivedPlans.value || status !== '已归档')
            : [defaultPurchasePlanStatus],
        sort_by: PLAN_SORTABLE_KEYS.includes(sortBy as PlanColumnKey)
          ? (sortBy as PlanColumnKey)
          : null,
        sort_order: sortOrder === 'asc' || sortOrder === 'desc' ? sortOrder : null,
      }
    },
    toQuery: (f) => ({
      name: f.name,
      model_spec: f.model_spec,
      actual_demand_person: f.actual_demand_person || undefined,
      subitem_no: f.subitem_no || undefined,
      category: f.category || undefined,
      status:
        f.status.length === 1 && f.status[0] === defaultPurchasePlanStatus
          ? undefined
          : f.status.join(','),
      sort_by: f.sort_by || undefined,
      sort_order: f.sort_order || undefined,
    }),
  },
})
const { searchName, applyExpandedName, clearExpandedName } = useImplicitAiSearch(() => filters.name)
const aiAvailable = ref(false)
const aiSearching = ref(false)
const resultExporting = ref(false)
const show = ref(false)
const editing = ref<PurchaseMaterial | null>(null)
const showBatch = ref(false)
const showBatchEdit = ref(false)
const saving = ref(false)
const deleting = ref(false)
const showHistory = ref(false)
const batchMoving = ref(false)
const batchUpdating = ref(false)
const batchExporting = ref(false)
const checkedRowKeys = ref<Array<string | number>>([])
const tableAreaRef = ref<HTMLElement | null>(null)
const isTableFullscreen = ref(false)
const formRef = ref<FormInst | null>(null)
const images = ref<FileObject[]>([])
const createPlanDate = ref(Date.now())
const createAdvancedSections = ref<string[]>([])
const filterOptions = ref<PurchaseFilterOptions>({
  actual_demand_persons: [],
  purchase_responsibles: [],
  subitem_nos: [],
  categories: [],
})
const actualDemandPersonOptions = computed(() => [
  { label: '空需求人', value: EMPTY_DEMAND_PERSON_FILTER },
  ...filterOptions.value.actual_demand_persons.map((value) => ({ label: value, value })),
])
const subitemOptions = computed(() => [
  { label: '空子项号', value: EMPTY_SUBITEM_FILTER },
  ...filterOptions.value.subitem_nos.map((value) => ({ label: value, value })),
])
const categoryOptions = computed(() => {
  const values = new Set([
    ...purchaseCategoryOptions.map((option) => option.value),
    ...filterOptions.value.categories,
  ])
  return [...values].map((value) => ({ label: value, value }))
})
const activeFilterCount = computed(
  () =>
    [
      filters.name.trim(),
      filters.model_spec.trim(),
      filters.actual_demand_person,
      filters.subitem_no,
      filters.category,
      filters.status.length === 1 && filters.status[0] === defaultPurchasePlanStatus
        ? ''
        : filters.status.join(','),
    ].filter(Boolean).length,
)
const batchForm = reactive({
  purchase_order_no: defaultPurchaseOrderNo(),
  trace_no: '',
  contract_no: '',
  vessel_no: '',
  consolidation_date: null as number | null,
  consolidation_port: '',
  sailing_date: null as number | null,
  purchase_date: Date.now(),
  salesperson: '',
  status: '已申购',
  record_remark: '',
})
const batchEditForm = reactive({
  update_plan_date: false,
  plan_date: null as number | null,
  update_category: false,
  category: '',
  update_urgency: false,
  urgency: defaultPurchaseUrgency,
  update_demand_department: false,
  demand_department: defaultDemandDepartment,
  update_actual_demand_person: false,
  actual_demand_person: '',
  update_purchase_responsible: false,
  purchase_responsible: '',
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
const exportOptions = computed<ExportOption[]>(() => {
  const options: ExportOption[] = [{ label: '导出查询结果', key: 'results' }]
  if (auth.can('purchase:write')) {
    options.push({
      label: `导出采购申请表（已选 ${selectedPlans.value.length} 条）`,
      key: 'purchase-application',
      disabled: !selectedPlans.value.length,
    })
  }
  return options
})
const exportLoading = computed(() => resultExporting.value || batchExporting.value)
const form = reactive<PurchaseMaterialWrite>({
  status: defaultPurchasePlanStatus,
  material_code: '',
  category: '',
  urgency: defaultPurchaseUrgency,
  demand_department: defaultDemandDepartment,
  name: '',
  model_spec: '',
  unit_name: '',
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
  actual_demand_person: { required: true, message: '请输入实际需求人' },
  purchase_responsible: { required: true, message: '请输入申购负责人' },
  planned_qty: [
    { required: true, message: '请输入计划数量' },
    {
      validator: () => Boolean(form.unit_name.trim()),
      message: '请输入计量单位',
      trigger: ['blur', 'change'],
    },
  ],
  usage: { required: true, message: '请输入用途' },
}
type PlanColumnKey =
  | 'plan_no'
  | 'plan_date'
  | 'material_code'
  | 'category'
  | 'urgency'
  | 'demand_department'
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
    column: {
      title: '计划 ID',
      key: 'plan_no',
      width: tableColumnWidths.identifier,
      render: (row) => renderTwoLineText(row.plan_no),
    },
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
        (row.material_code && renderTwoLineText(row.material_code)) ||
        h(NTag, { type: 'warning', size: 'small' }, { default: () => '暂无编码' }),
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
    key: 'urgency',
    label: '紧急程度',
    column: {
      title: '紧急程度',
      key: 'urgency',
      width: tableColumnWidths.person,
      render: (row) => renderTwoLineText(row.urgency),
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
    key: 'name',
    label: '名称',
    column: {
      title: '名称',
      key: 'name',
      width: tableColumnWidths.name,
      render: (row) => renderTwoLineText(row.name),
    },
  },
  {
    key: 'model_spec',
    label: '型号规格',
    column: {
      title: '型号规格',
      key: 'model_spec',
      width: tableColumnWidths.model,
      render: (row) => renderTwoLineText(row.model_spec),
    },
  },
  {
    key: 'planned_qty',
    label: '计划数量',
    column: { title: '计划数量', key: 'planned_qty', width: tableColumnWidths.quantity },
  },
  {
    key: 'unit_name',
    label: '计量单位',
    column: {
      title: '计量单位',
      key: 'unit_name',
      width: tableColumnWidths.unit,
      render: (row) => renderTwoLineText(row.unit_name),
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
    key: 'subitem_no',
    label: '子项号',
    column: {
      title: '子项号',
      key: 'subitem_no',
      width: tableColumnWidths.person,
      render: (row) => renderTwoLineText(row.subitem_no),
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
]
const visibleColumnKeys = ref<PlanColumnKey[]>(availableColumns.map((item) => item.key))
const fieldOptions = availableColumns.map((item) => ({ label: item.label, value: item.key }))
const columns = computed<DataTableColumns<PurchaseMaterial>>(() => {
  const sortBy = filters.sort_by
  const sortOrder = filters.sort_order
  return preventTableColumnCompression([
    {
      type: 'selection',
      disabled: () => !auth.can('purchase:write'),
    },
    ...availableColumns
      .filter((item) => visibleColumnKeys.value.includes(item.key))
      .map((item) => ({
        ...item.column,
        // 列头改为下拉菜单（默认/升序/降序），不再用 Naive UI 的内置点击循环
        title: () =>
          h(SortableHeader, {
            label: item.label,
            sortByKey: item.key,
            sortBy,
            sortOrder,
            onSelect: (order) => handleSortSelect(item.key, order),
          }),
      })),
  ])
})
function handleSortSelect(key: PlanColumnKey, order: SortOptionKey) {
  if (order === 'default') {
    filters.sort_by = null
    filters.sort_order = null
  } else {
    filters.sort_by = key
    filters.sort_order = order
  }
  void query()
}
const tableScrollX = computed(() => getTableScrollX(columns.value))
useShiftWheelHorizontalScroll(tableAreaRef)
function setVisibleColumnKeys(value: string[]) {
  visibleColumnKeys.value = value as PlanColumnKey[]
}
function rowProps(row: PurchaseMaterial) {
  return {
    style: 'cursor: pointer',
    onMousedown: rowClickGuard.onMouseDown,
    onClick: (event: MouseEvent) => {
      if (rowClickGuard.shouldIgnore(event)) return
      // 点击行直接打开编辑弹窗（与「新建」共用同一弹窗）
      openEdit(row)
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
        filters.subitem_no && filters.subitem_no !== EMPTY_SUBITEM_FILTER
          ? filters.subitem_no
          : undefined,
      empty_subitem_no: filters.subitem_no === EMPTY_SUBITEM_FILTER,
      category: filters.category || undefined,
      status: filters.status.length ? filters.status : undefined,
      sort_by: filters.sort_by || undefined,
      sort_order: filters.sort_order || 'asc',
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
function openCreate() {
  editing.value = null
  Object.assign(form, {
    status: defaultPurchasePlanStatus,
    material_code: '',
    category: '',
    urgency: defaultPurchaseUrgency,
    demand_department: defaultDemandDepartment,
    name: '',
    model_spec: '',
    unit_name: '',
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
  createAdvancedSections.value = []
  show.value = true
}
function openEdit(row: PurchaseMaterial) {
  editing.value = row
  Object.assign(form, {
    status: row.status,
    material_code: row.material_code || '',
    category: row.category || '',
    urgency: row.urgency,
    demand_department: row.demand_department,
    name: row.name,
    model_spec: row.model_spec,
    unit_name: row.unit_name,
    actual_demand_person: row.actual_demand_person,
    purchase_responsible: row.purchase_responsible,
    planned_qty: row.planned_qty,
    usage: row.usage,
    subitem_no: row.subitem_no || '',
    stock_material_id: row.stock_material_id,
    remark: row.remark || '',
    image_ids: row.images.map((image) => image.id),
    version: row.version,
  })
  images.value = [...row.images]
  createPlanDate.value = dateToTimestamp(row.plan_date)
  createAdvancedSections.value = []
  show.value = true
}
function applyMaterialCode(item: MaterialCodeLibrary) {
  form.material_code = item.material_code
  if (item.name?.trim()) form.name = item.name
  if (item.model_spec?.trim()) form.model_spec = item.model_spec
  form.unit_name = item.unit_name
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
    const payload = {
      ...form,
      plan_date: toShanghaiDate(createPlanDate.value),
      subitem_no: form.subitem_no?.trim() || undefined,
    }
    if (editing.value) {
      await procurementApi.updateMaterial(editing.value.id, payload)
      message.success('申购计划已保存')
    } else {
      await procurementApi.createMaterial(payload)
      rememberPurchaseResponsible(form.purchase_responsible || '')
      message.success('申购计划已创建')
    }
    show.value = false
    editing.value = null
    page.value = 1
    await Promise.all([load(), loadFilterOptions()])
  } catch (e) {
    message.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}
function openInNewPage() {
  const target = editing.value
  if (!target) return
  show.value = false
  editing.value = null
  void router.push(`/procurement/materials/${target.id}`)
}
async function deletePlan() {
  const target = editing.value
  if (!target) return
  deleting.value = true
  try {
    await procurementApi.deleteMaterial(target.id, target.version)
    message.success('申购计划已删除')
    show.value = false
    editing.value = null
    // 防空页：删除的是当前页最后一条且非第一页时回退一页
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    await Promise.all([load(), loadFilterOptions()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '删除失败')
  } finally {
    deleting.value = false
  }
}
function confirmDelete() {
  const target = editing.value
  if (!target) return
  if (target.moved_to_record) {
    message.warning('已转入申购记录的计划不能删除')
    return
  }
  dialog.warning({
    draggable: true,
    title: '删除申购计划',
    content: `确认删除“${target.name}”的这条申购计划吗？删除后不可恢复。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: deletePlan,
  })
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
    contract_no: '',
    vessel_no: '',
    consolidation_date: null,
    consolidation_port: '',
    sailing_date: null,
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
    update_category: false,
    category: '',
    update_urgency: false,
    urgency: defaultPurchaseUrgency,
    update_demand_department: false,
    demand_department: defaultDemandDepartment,
    update_actual_demand_person: false,
    actual_demand_person: '',
    update_purchase_responsible: false,
    purchase_responsible: '',
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
  if (batchEditForm.update_category) {
    payload.category = batchEditForm.category.trim() || null
  }
  if (batchEditForm.update_urgency) {
    payload.urgency = batchEditForm.urgency
  }
  if (batchEditForm.update_demand_department) {
    if (!batchEditForm.demand_department.trim()) {
      message.error('请输入需求部门')
      return
    }
    payload.demand_department = batchEditForm.demand_department.trim()
  }
  if (batchEditForm.update_actual_demand_person) {
    if (!batchEditForm.actual_demand_person.trim()) {
      message.error('请输入实际需求人')
      return
    }
    payload.actual_demand_person = batchEditForm.actual_demand_person.trim()
  }
  if (batchEditForm.update_purchase_responsible) {
    if (!batchEditForm.purchase_responsible.trim()) {
      message.error('请输入申购负责人')
      return
    }
    payload.purchase_responsible = batchEditForm.purchase_responsible.trim()
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
        contract_no: batchForm.contract_no.trim() || null,
        vessel_no: batchForm.vessel_no.trim() || null,
        consolidation_date: batchForm.consolidation_date
          ? toShanghaiDate(batchForm.consolidation_date)
          : undefined,
        consolidation_port: batchForm.consolidation_port.trim() || null,
        sailing_date: batchForm.sailing_date ? toShanghaiDate(batchForm.sailing_date) : undefined,
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
  const requiredFields = [
    { label: '编码', missing: (item: PurchaseMaterial) => !item.material_code?.trim() },
    { label: '子项号', missing: (item: PurchaseMaterial) => !item.subitem_no?.trim() },
    { label: '用途', missing: (item: PurchaseMaterial) => !item.usage?.trim() },
  ]
  const missingLabels = requiredFields
    .filter(({ missing }) => selectedPlans.value.some(missing))
    .map(({ label }) => label)
  if (missingLabels.length) {
    message.warning(`导出采购申请表前请补全：${missingLabels.join('、')}`)
    return
  }
  batchExporting.value = true
  try {
    const content = await procurementApi.exportPurchaseApplication(
      selectedPlans.value.map((item) => item.id),
    )
    const date = toShanghaiDate(Date.now()).replace(/-/g, '')
    downloadBlob(content, `采购申请表_${date}.xlsx`)
    message.success('采购申请表已导出')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    batchExporting.value = false
  }
}
function handleExport(key: string) {
  if (key === 'results') {
    void exportResults()
    return
  }
  if (key === 'purchase-application') void exportPurchaseApplication()
}
onMounted(() => {
  document.addEventListener('fullscreenchange', syncTableFullscreen)
  void loadFilterOptions()
  void loadAiStatus()
  // 列表首载由 usePagedTable（immediate）触发
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
      <n-space>
        <ExportButton :options="exportOptions" :loading="exportLoading" @select="handleExport" />
        <template v-if="auth.can('purchase:write')">
          <n-button :disabled="!selectedPlans.length" @click="openBatchEdit">
            批量修改（{{ selectedPlans.length }}）
          </n-button>
          <n-button :disabled="!selectedPlans.length" @click="openBatchMove">
            批量转为申购记录（{{ selectedPlans.length }}）
          </n-button>
          <n-button type="primary" @click="openCreate">新建申购计划</n-button>
        </template>
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
          <n-select
            v-model:value="filters.subitem_no"
            :options="subitemOptions"
            placeholder="选择或搜索子项号"
            filterable
            clearable
          />
        </label>
        <label class="filter-field">
          <span>类别</span>
          <n-select
            v-model:value="filters.category"
            :options="categoryOptions"
            placeholder="选择类别"
            filterable
            clearable
          />
        </label>
        <label class="filter-field">
          <span>申购状态</span>
          <n-select
            v-model:value="filters.status"
            class="status-filter-select"
            :options="statusFilterOptions"
            multiple
            clearable
            placeholder="选择一个或多个状态"
          />
        </label>
      </div>
      <div class="filter-actions">
        <ColumnVisibilityPicker
          :value="visibleColumnKeys"
          :options="fieldOptions"
          storage-key="procurement.purchase-materials.visible-columns.v3"
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
          :remote="true"
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
      draggable
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
              <n-checkbox v-model:checked="batchEditForm.update_category">修改类别</n-checkbox>
            </template>
            <n-select
              v-model:value="batchEditForm.category"
              :options="categoryOptions"
              filterable
              clearable
              placeholder="留空将清除类别"
              :disabled="!batchEditForm.update_category"
            />
          </n-form-item>
          <n-form-item>
            <template #label>
              <n-checkbox v-model:checked="batchEditForm.update_urgency"> 修改紧急程度 </n-checkbox>
            </template>
            <n-select
              v-model:value="batchEditForm.urgency"
              :options="purchaseUrgencyOptions"
              :disabled="!batchEditForm.update_urgency"
            />
          </n-form-item>
          <n-form-item>
            <template #label>
              <n-checkbox v-model:checked="batchEditForm.update_demand_department">
                修改需求部门
              </n-checkbox>
            </template>
            <n-input
              v-model:value="batchEditForm.demand_department"
              maxlength="128"
              :disabled="!batchEditForm.update_demand_department"
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
              <n-checkbox v-model:checked="batchEditForm.update_purchase_responsible">
                修改申购负责人
              </n-checkbox>
            </template>
            <n-input
              v-model:value="batchEditForm.purchase_responsible"
              maxlength="128"
              :disabled="!batchEditForm.update_purchase_responsible"
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
      draggable
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
          <n-form-item label="合同号">
            <n-input v-model:value="batchForm.contract_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="船号">
            <n-input v-model:value="batchForm.vessel_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="集港日期">
            <n-date-picker
              v-model:value="batchForm.consolidation_date"
              type="date"
              class="full-width"
              clearable
            />
          </n-form-item>
          <n-form-item label="集港港口">
            <n-input
              v-model:value="batchForm.consolidation_port"
              maxlength="128"
              placeholder="可留空"
            />
          </n-form-item>
          <n-form-item label="发船日期">
            <n-date-picker
              v-model:value="batchForm.sailing_date"
              type="date"
              class="full-width"
              clearable
            />
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
      draggable
      :title="editing ? '编辑申购计划' : '新建申购计划'"
      style="width: 680px"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <div class="form-grid">
          <n-form-item label="需求日期" required>
            <n-date-picker v-model:value="createPlanDate" type="date" class="full-width" />
          </n-form-item>
          <n-form-item label="物料编码">
            <MaterialCodeSelector
              :model-value="form.material_code || ''"
              :default-name="form.name"
              :default-model-spec="form.model_spec"
              @update:model-value="form.material_code = $event"
              @select="applyMaterialCode"
            />
          </n-form-item>
          <n-form-item label="名称" path="name">
            <n-input v-model:value="form.name" maxlength="128">
              <template #suffix>
                <n-button text type="primary" size="tiny" @click="showHistory = true"
                  >查历史</n-button
                >
              </template>
            </n-input>
          </n-form-item>
          <n-form-item label="型号规格" path="model_spec">
            <n-input v-model:value="form.model_spec" maxlength="255" />
          </n-form-item>
          <n-form-item label="紧急程度">
            <n-select v-model:value="form.urgency" :options="purchaseUrgencyOptions" />
          </n-form-item>
          <n-form-item label="计划数量 / 计量单位" path="planned_qty">
            <n-input-group>
              <QuantityInput
                v-model:value="form.planned_qty"
                :decimal-places="1"
                class="quantity-input"
              />
              <n-input
                v-model:value="form.unit_name"
                maxlength="32"
                placeholder="计量单位"
                class="quantity-unit-select"
              />
            </n-input-group>
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
        <n-collapse v-model:expanded-names="createAdvancedSections" class="create-advanced-fields">
          <n-collapse-item name="advanced">
            <template #header>
              <span class="advanced-header">更多设置</span>
            </template>
            <div class="form-grid">
              <n-form-item label="状态" required>
                <n-select v-model:value="form.status" :options="purchasePlanStatusOptions" />
              </n-form-item>
              <n-form-item label="类别">
                <n-select
                  v-model:value="form.category"
                  :options="categoryOptions"
                  filterable
                  clearable
                  placeholder="选择类别"
                />
              </n-form-item>
              <n-form-item label="需求部门">
                <n-input v-model:value="form.demand_department" maxlength="128" />
              </n-form-item>
              <n-form-item label="关联二级库物资">
                <MaterialSelector
                  :value="form.stock_material_id ?? null"
                  @update:value="form.stock_material_id = $event ?? undefined"
                />
              </n-form-item>
            </div>
          </n-collapse-item>
        </n-collapse>
        <n-form-item label="备注"
          ><n-input v-model:value="form.remark" type="textarea" maxlength="1000" show-count
        /></n-form-item>
        <n-form-item label="图片附件"><ImageUploader v-model:files="images" /></n-form-item></n-form
      ><template #footer
        ><n-space justify="space-between"
          ><template v-if="editing"
            ><n-space justify="start"
              ><n-button
                v-if="auth.can('purchase:write')"
                type="error"
                text
                :loading="deleting"
                :disabled="editing.moved_to_record"
                @click="confirmDelete"
                >删除</n-button
              ><n-button text type="primary" class="open-new-page-btn" @click="openInNewPage"
                >在新页面查看</n-button
              ></n-space
            ></template
          ><span v-else></span
          ><n-space justify="end"
            ><n-button @click="show = false">取消</n-button
            ><n-button type="primary" :loading="saving" @click="save">保存</n-button></n-space
          ></n-space
        ></template
      ></n-modal
    >
    <PurchaseRecordHistoryDialog v-model:show="showHistory" :initial-name="form.name" />
  </div>
</template>

<style scoped>
.quantity-input {
  flex: 1;
}

.quantity-unit-select {
  width: 160px;
}

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

.status-filter-select :deep(.n-base-selection-tags) {
  min-height: 34px;
  padding: 4px 30px 1px 10px;
}

.status-filter-select :deep(.n-base-selection-tag-wrapper) {
  padding: 0 6px 3px 0;
}

.status-filter-select :deep(.n-base-selection-placeholder) {
  padding: 0 30px 0 10px;
}

.create-advanced-fields {
  margin-bottom: 18px;
  overflow: hidden;
  border-radius: 8px;
  background: #f6f8fb;
}

.create-advanced-fields :deep(.n-collapse-item) {
  border-radius: 8px;
}

.create-advanced-fields :deep(.n-collapse-item__header) {
  padding: 10px 12px;
  transition: background-color 0.2s ease;
}

.create-advanced-fields :deep(.n-collapse-item__header:hover) {
  background: #eef2f9;
}

.create-advanced-fields :deep(.n-collapse-item__content-inner) {
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
