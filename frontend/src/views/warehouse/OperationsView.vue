<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { StockOperation } from '@/api/generated'
import { inventoryApi } from '@/api/inventory'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import { formatShanghaiTime } from '@/utils/time'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'

const router = useRouter()
const message = useMessage()
const rowClickGuard = createTableRowClickGuard()
const items = ref<StockOperation[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dateRange = ref<[number, number] | null>(null)
const filters = reactive({
  operation_no: '',
  operation_type: null as string | null,
  material_name: '',
})
const columns = preventTableColumnCompression<StockOperation>([
  {
    title: '流水号',
    key: 'operation_no',
    width: tableColumnWidths.identifier,
    render: (row) =>
      h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: () => router.push({ name: 'operation-detail', params: { id: row.id } }),
        },
        { default: () => row.operation_no },
      ),
  },
  {
    title: '类型',
    key: 'operation_type',
    width: 90,
    render: (row) =>
      h(
        NTag,
        { type: row.operation_type === 'INBOUND' ? 'success' : 'warning' },
        { default: () => (row.operation_type === 'INBOUND' ? '入库' : '出库') },
      ),
  },
  {
    title: '发生时间',
    key: 'occurred_at',
    width: tableColumnWidths.datetime,
    render: (row) => formatShanghaiTime(row.occurred_at),
  },
  {
    title: '物资',
    key: 'lines',
    width: tableColumnWidths.material,
    ellipsis: { tooltip: true },
    render: (row) => row.lines.map((line) => `${line.material_name} × ${line.quantity}`).join('；'),
  },
  {
    title: '用途',
    key: 'business_reason',
    width: tableColumnWidths.text,
    ellipsis: { tooltip: true },
  },
  {
    title: '操作',
    key: 'action',
    width: 80,
    render: (row) =>
      h(
        NButton,
        {
          size: 'small',
          onClick: () => router.push({ name: 'operation-detail', params: { id: row.id } }),
        },
        { default: () => '详情' },
      ),
  },
])
const tableScrollX = getTableScrollX(columns)

async function load() {
  loading.value = true
  try {
    const data = await inventoryApi.operations({
      page: page.value,
      page_size: pageSize.value,
      operation_no: filters.operation_no.trim() || undefined,
      operation_type: filters.operation_type || undefined,
      material_name: filters.material_name.trim() || undefined,
      start_at: dateRange.value ? new Date(dateRange.value[0]).toISOString() : undefined,
      end_at: dateRange.value ? new Date(dateRange.value[1]).toISOString() : undefined,
    })
    items.value = data.items
    total.value = data.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : '操作记录查询失败')
  } finally {
    loading.value = false
  }
}

function query() {
  page.value = 1
  void load()
}
function changePage(nextPage: number) {
  page.value = nextPage
  void load()
}
function changePageSize(nextPageSize: number) {
  pageSize.value = nextPageSize
  page.value = 1
  void load()
}

function resetFilters() {
  Object.assign(filters, { operation_no: '', operation_type: null, material_name: '' })
  dateRange.value = null
  query()
}

function rowProps(row: StockOperation) {
  return {
    style: 'cursor: pointer',
    onMousedown: rowClickGuard.onMouseDown,
    onClick: (event: MouseEvent) => {
      if (!rowClickGuard.shouldIgnore(event)) {
        void router.push({ name: 'operation-detail', params: { id: row.id } })
      }
    },
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">操作记录</h1>
      </div>
    </div>

    <n-card class="filter-card" :bordered="false">
      <div class="filter-heading">
        <div>
          <div class="filter-title">筛选条件</div>
        </div>
      </div>
      <div class="warehouse-filter-grid">
        <label class="filter-field">
          <span>流水号</span>
          <n-input
            v-model:value="filters.operation_no"
            clearable
            placeholder="输入流水号"
            @keyup.enter="query"
          />
        </label>
        <label class="filter-field">
          <span>操作类型</span>
          <n-select
            v-model:value="filters.operation_type"
            clearable
            :options="[
              { label: '入库', value: 'INBOUND' },
              { label: '出库', value: 'OUTBOUND' },
            ]"
            placeholder="选择操作类型"
          />
        </label>
        <label class="filter-field">
          <span>物资名称或型号规格</span>
          <n-input
            v-model:value="filters.material_name"
            clearable
            placeholder="输入物资名称或型号规格"
            @keyup.enter="query"
          />
        </label>
        <label class="filter-field">
          <span>发生时间</span>
          <n-date-picker
            v-model:value="dateRange"
            type="datetimerange"
            clearable
            class="full-width"
          />
        </label>
      </div>
      <div class="filter-actions">
        <n-button @click="resetFilters">重置</n-button>
        <n-button type="primary" :loading="loading" @click="query">查询</n-button>
      </div>
    </n-card>

    <n-card class="data-card" :bordered="false">
      <n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-props="rowProps"
        :scroll-x="tableScrollX"
        :row-key="(row: StockOperation) => row.id"
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

.warehouse-filter-grid {
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

.filter-actions {
  justify-content: flex-end;
  margin-top: 20px;
}

@media (max-width: 1100px) {
  .warehouse-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .warehouse-filter-grid {
    grid-template-columns: 1fr;
  }
}
</style>
