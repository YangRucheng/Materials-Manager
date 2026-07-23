<script setup lang="ts">
import { computed, h, onActivated, onMounted, reactive, ref } from 'vue'
import { NTag, useMessage, type DataTableBaseColumn, type DataTableColumns } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import type { PurchaseRecord, PurchaseRecordFilterOptions } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { aiSearchApi } from '@/api/aiSearch'
import ColumnVisibilityPicker from '@/components/ColumnVisibilityPicker.vue'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'
import { formatDate, toShanghaiDate } from '@/utils/time'
import { downloadBlob } from '@/utils/download'
import { compactRouteQuery, routeQueryPositiveInteger, routeQueryString } from '@/utils/routeQuery'
import { useImplicitAiSearch } from '@/composables/useImplicitAiSearch'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const rowClickGuard = createTableRowClickGuard()
const items = ref<PurchaseRecord[]>([])
const loading = ref(false)
const aiAvailable = ref(false)
const aiSearching = ref(false)
const resultExporting = ref(false)
const total = ref(0)
const page = ref(routeQueryPositiveInteger(route.query.page, 1))
const pageSize = ref(routeQueryPositiveInteger(route.query.page_size, 20))
const EMPTY_STATUS_FILTER = '__empty_status__'
const filters = reactive({
  purchase_order_no: routeQueryString(route.query.purchase_order_no),
  trace_no: routeQueryString(route.query.trace_no),
  name: routeQueryString(route.query.name),
  model_spec: routeQueryString(route.query.model_spec),
  purchase_responsible: routeQueryString(route.query.purchase_responsible) || null,
  salesperson: routeQueryString(route.query.salesperson) || null,
  status: routeQueryString(route.query.status) || null,
})
const { searchName, applyExpandedName, clearExpandedName } = useImplicitAiSearch(() => filters.name)
const filterOptions = ref<PurchaseRecordFilterOptions>({
  actual_demand_persons: [],
  purchase_responsibles: [],
  subitem_nos: [],
  salespersons: [],
  statuses: [],
})
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
const activeFilterCount = computed(
  () => Object.values(filters).filter((value) => value?.trim()).length,
)
type RecordColumnKey =
  | 'plan_date'
  | 'purchase_order_no'
  | 'trace_no'
  | 'material_name'
  | 'purchase_qty'
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
    key: 'purchase_qty',
    label: '申购数量',
    column: {
      title: '申购数量',
      key: 'purchase_qty',
      width: tableColumnWidths.quantity,
      render: (row) => `${row.purchase_qty} ${row.unit_name}`,
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
    key: 'purchase_order_no',
    label: '申购单号',
    column: {
      title: '申购单号',
      key: 'purchase_order_no',
      width: tableColumnWidths.identifier,
      render: (row) => row.purchase_order_no || '\\',
    },
  },
  {
    key: 'trace_no',
    label: '追溯号',
    column: {
      title: '追溯号',
      key: 'trace_no',
      width: tableColumnWidths.identifier,
      render: (row) => row.trace_no || '\\',
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
        h('div', [
          h('strong', row.material_name),
          h('div', { class: 'muted' }, `${row.material_code || '\\'}｜${row.model_spec}`),
        ]),
    },
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
    key: 'salesperson',
    label: '业务员',
    column: {
      title: '业务员',
      key: 'salesperson',
      width: tableColumnWidths.person,
      render: (row) => row.salesperson || '\\',
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
]
const visibleColumnKeys = ref<RecordColumnKey[]>(availableColumns.map((item) => item.key))
const fieldOptions = availableColumns.map((item) => ({ label: item.label, value: item.key }))
const columns = computed<DataTableColumns<PurchaseRecord>>(() =>
  preventTableColumnCompression(
    availableColumns
      .filter((item) => visibleColumnKeys.value.includes(item.key))
      .map((item) => item.column),
  ),
)
const tableScrollX = computed(() => getTableScrollX(columns.value))
function setVisibleColumnKeys(value: string[]) {
  visibleColumnKeys.value = value as RecordColumnKey[]
}
function rowProps(row: PurchaseRecord) {
  return {
    style: 'cursor: pointer',
    onMousedown: rowClickGuard.onMouseDown,
    onClick: (event: MouseEvent) => {
      if (rowClickGuard.shouldIgnore(event)) return
      void router.push(`/procurement/records/${row.line_id}`)
    },
  }
}

async function load() {
  loading.value = true
  try {
    const data = await procurementApi.records({
      page: page.value,
      page_size: pageSize.value,
      purchase_order_no: filters.purchase_order_no.trim() || undefined,
      trace_no: filters.trace_no.trim() || undefined,
      name: searchName.value,
      model_spec: filters.model_spec.trim() || undefined,
      purchase_responsible: filters.purchase_responsible?.trim() || undefined,
      salesperson: filters.salesperson?.trim() || undefined,
      status: filters.status && filters.status !== EMPTY_STATUS_FILTER ? filters.status : undefined,
      empty_status: filters.status === EMPTY_STATUS_FILTER || undefined,
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
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

async function syncRoute() {
  await router.replace({
    name: 'purchase-records',
    query: compactRouteQuery({
      page: page.value === 1 ? undefined : page.value,
      page_size: pageSize.value === 20 ? undefined : pageSize.value,
      purchase_order_no: filters.purchase_order_no,
      trace_no: filters.trace_no,
      name: filters.name,
      model_spec: filters.model_spec,
      purchase_responsible: filters.purchase_responsible,
      salesperson: filters.salesperson,
      status: filters.status,
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
    const content = await procurementApi.exportRecordResults({
      columns: exportColumns,
      purchase_order_no: filters.purchase_order_no.trim() || undefined,
      trace_no: filters.trace_no.trim() || undefined,
      name: searchName.value,
      model_spec: filters.model_spec.trim() || undefined,
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

function resetFilters() {
  filters.purchase_order_no = ''
  filters.trace_no = ''
  filters.name = ''
  filters.model_spec = ''
  filters.purchase_responsible = null
  filters.salesperson = null
  filters.status = null
  query()
}

function changePageSize() {
  void syncRouteAndLoad(true)
}

function changePage() {
  void syncRouteAndLoad()
}

onMounted(() => {
  void loadFilterOptions()
  void loadAiStatus()
  void load()
})
onActivated(() => {
  void syncRoute()
})
</script>

<template>
  <div class="page purchase-records-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">申购记录</h1>
      </div>
      <n-tag :bordered="false" round type="info">共 {{ total }} 条记录</n-tag>
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
          <span>申购单号</span>
          <n-input
            v-model:value="filters.purchase_order_no"
            placeholder="输入申购单号"
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
          <span>型号规格</span>
          <n-input
            v-model:value="filters.model_spec"
            placeholder="输入型号规格"
            clearable
            @keyup.enter="query"
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
          storage-key="procurement.purchase-records.visible-columns.v1"
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
    <n-card class="records-card data-card" :bordered="false">
      <n-data-table
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
</style>
