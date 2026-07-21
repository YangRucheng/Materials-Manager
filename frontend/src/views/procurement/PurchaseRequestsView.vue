<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NTag, type DataTableBaseColumn, type DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { PurchaseRecord, PurchaseRecordFilterOptions } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import ColumnVisibilityPicker from '@/components/ColumnVisibilityPicker.vue'
import { formatDate } from '@/utils/time'

const router = useRouter()
const items = ref<PurchaseRecord[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const EMPTY_STATUS_FILTER = '__empty_status__'
type RecordSearchField =
  | 'plan_no'
  | 'plan_date'
  | 'purchase_order_no'
  | 'trace_no'
  | 'material_code'
  | 'material_name'
  | 'model_spec'
  | 'unit_name'
  | 'purchase_qty'
  | 'salesperson'
  | 'status'
  | 'purchase_date'
  | 'usage'
  | 'subitem_no'
  | 'plan_remark'
  | 'record_remark'
const filters = reactive({
  search_field: 'material_name' as RecordSearchField,
  search_value: '',
  actual_demand_person: null as string | null,
  purchase_responsible: null as string | null,
  status: null as string | null,
})
const filterOptions = ref<PurchaseRecordFilterOptions>({
  actual_demand_persons: [],
  purchase_responsibles: [],
  statuses: [],
})
const searchFieldOptions: Array<{ label: string; value: RecordSearchField }> = [
  { label: '计划 ID', value: 'plan_no' },
  { label: '需求日期', value: 'plan_date' },
  { label: '申购单号', value: 'purchase_order_no' },
  { label: '追溯号', value: 'trace_no' },
  { label: '物料编码', value: 'material_code' },
  { label: '物资名称', value: 'material_name' },
  { label: '型号规格', value: 'model_spec' },
  { label: '单位', value: 'unit_name' },
  { label: '申购数量', value: 'purchase_qty' },
  { label: '业务员', value: 'salesperson' },
  { label: '状态', value: 'status' },
  { label: '申购日期', value: 'purchase_date' },
  { label: '用途', value: 'usage' },
  { label: '子项号', value: 'subitem_no' },
  { label: '计划备注', value: 'plan_remark' },
  { label: '记录备注', value: 'record_remark' },
]
const actualDemandPersonOptions = computed(() =>
  filterOptions.value.actual_demand_persons.map((value) => ({ label: value, value })),
)
const purchaseResponsibleOptions = computed(() =>
  filterOptions.value.purchase_responsibles.map((value) => ({ label: value, value })),
)
const statusOptions = computed(() => [
  { label: '空状态', value: EMPTY_STATUS_FILTER },
  ...filterOptions.value.statuses.map((value) => ({ label: value, value })),
])
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
      width: 110,
      render: (row) => `${row.purchase_qty} ${row.unit_name}`,
    },
  },
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
    key: 'purchase_order_no',
    label: '申购单号',
    column: {
      title: '申购单号',
      key: 'purchase_order_no',
      width: 170,
      render: (row) => row.purchase_order_no || '未填写',
    },
  },
  {
    key: 'trace_no',
    label: '追溯号',
    column: {
      title: '追溯号',
      key: 'trace_no',
      width: 170,
      render: (row) => row.trace_no || '—',
    },
  },
  {
    key: 'material_name',
    label: '物资',
    column: {
      title: '物资',
      key: 'material_name',
      render: (row) =>
        h('div', [
          h('strong', row.material_name),
          h('div', { class: 'muted' }, `${row.material_code}｜${row.model_spec}`),
        ]),
    },
  },
  {
    key: 'actual_demand_person',
    label: '实际需求人',
    column: { title: '实际需求人', key: 'actual_demand_person', width: 110 },
  },
  {
    key: 'purchase_responsible',
    label: '申购负责人',
    column: { title: '申购负责人', key: 'purchase_responsible', width: 110 },
  },
  {
    key: 'salesperson',
    label: '业务员',
    column: {
      title: '业务员',
      key: 'salesperson',
      width: 110,
      render: (row) => row.salesperson || '—',
    },
  },
  {
    key: 'status',
    label: '状态',
    column: {
      title: '状态',
      key: 'status',
      width: 120,
      render: (row) => h(NTag, null, { default: () => row.status }),
    },
  },
  {
    key: 'purchase_date',
    label: '申购日期',
    column: {
      title: '申购日期',
      key: 'purchase_date',
      width: 120,
      render: (row) => formatDate(row.purchase_date),
    },
  },
]
const visibleColumnKeys = ref<RecordColumnKey[]>(availableColumns.map((item) => item.key))
const fieldOptions = availableColumns.map((item) => ({ label: item.label, value: item.key }))
const columns = computed<DataTableColumns<PurchaseRecord>>(() =>
  availableColumns
    .filter((item) => visibleColumnKeys.value.includes(item.key))
    .map((item) => item.column),
)
function setVisibleColumnKeys(value: string[]) {
  visibleColumnKeys.value = value as RecordColumnKey[]
}
function rowProps(row: PurchaseRecord) {
  return {
    style: 'cursor: pointer',
    onClick: () => {
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
      search_field: filters.search_field,
      search_value: filters.search_value.trim() || undefined,
      actual_demand_person: filters.actual_demand_person || undefined,
      purchase_responsible: filters.purchase_responsible || undefined,
      status:
        filters.status && filters.status !== EMPTY_STATUS_FILTER ? filters.status : undefined,
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

function query() {
  page.value = 1
  void load()
}

function resetFilters() {
  filters.search_field = 'material_name'
  filters.search_value = ''
  filters.actual_demand_person = null
  filters.purchase_responsible = null
  filters.status = null
  query()
}

function changePageSize() {
  page.value = 1
  void load()
}

onMounted(() => {
  void loadFilterOptions()
  void load()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">申购记录</h1>
        <p class="page-subtitle">用于整理和统计正式申购信息</p>
      </div>
    </div>
    <n-card>
      <div class="filter-bar">
        <n-select
          v-model:value="filters.search_field"
          :options="searchFieldOptions"
          style="width: 140px"
        />
        <n-input
          v-model:value="filters.search_value"
          placeholder="输入模糊搜索内容"
          clearable
          style="width: 220px"
          @keyup.enter="query"
        />
        <n-select
          v-model:value="filters.actual_demand_person"
          :options="actualDemandPersonOptions"
          placeholder="实际需求人"
          filterable
          clearable
          style="width: 160px"
        />
        <n-select
          v-model:value="filters.purchase_responsible"
          :options="purchaseResponsibleOptions"
          placeholder="申购负责人"
          filterable
          clearable
          style="width: 160px"
        />
        <n-select
          v-model:value="filters.status"
          :options="statusOptions"
          clearable
          filterable
          placeholder="状态"
          style="width: 150px"
        />
        <ColumnVisibilityPicker
          :value="visibleColumnKeys"
          :options="fieldOptions"
          storage-key="procurement.purchase-records.visible-columns.v1"
          @update:value="setVisibleColumnKeys"
        />
        <n-button type="primary" @click="query">查询</n-button>
        <n-button @click="resetFilters">重置</n-button>
      </div>
    </n-card>
    <n-card>
      <n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-props="rowProps"
        :row-key="(row: PurchaseRecord) => row.line_id"
      />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :item-count="total"
          :page-sizes="[10, 20, 50, 100, 200]"
          show-size-picker
          @update:page="load"
          @update:page-size="changePageSize"
        />
      </div>
    </n-card>
  </div>
</template>
