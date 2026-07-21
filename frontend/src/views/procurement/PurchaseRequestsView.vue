<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NTag, type DataTableBaseColumn, type DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { PurchaseRecord } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import ColumnVisibilityPicker from '@/components/ColumnVisibilityPicker.vue'
import { formatDate } from '@/utils/time'

const router = useRouter()
const items = ref<PurchaseRecord[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filters = reactive({
  name: '',
  model_spec: '',
  purchase_responsible: '',
  status: '',
})
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
      name: filters.name.trim() || undefined,
      model_spec: filters.model_spec.trim() || undefined,
      purchase_responsible: filters.purchase_responsible.trim() || undefined,
      status: filters.status || undefined,
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function query() {
  page.value = 1
  void load()
}

function resetFilters() {
  filters.name = ''
  filters.model_spec = ''
  filters.purchase_responsible = ''
  filters.status = ''
  query()
}

function changePageSize() {
  page.value = 1
  void load()
}

onMounted(() => {
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
        <n-input
          v-model:value="filters.purchase_responsible"
          placeholder="申购人"
          clearable
          style="width: 180px"
          @keyup.enter="query"
        />
        <n-input
          v-model:value="filters.status"
          clearable
          placeholder="状态（模糊）"
          style="width: 150px"
          @keyup.enter="query"
        />
        <ColumnVisibilityPicker
          :value="visibleColumnKeys"
          :options="fieldOptions"
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
