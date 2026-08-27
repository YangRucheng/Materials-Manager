<script setup lang="ts">
import { h, ref } from 'vue'
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
import { usePagedTable } from '@/composables/usePagedTable'
import FilterExpandButton from '@/components/FilterExpandButton.vue'

const router = useRouter()
const message = useMessage()
const rowClickGuard = createTableRowClickGuard()
const filterExpanded = ref(false)
type OperationFilters = {
  operation_no: string
  operation_type: string | null
  material_name: string
  dateRange: [number, number] | null
}
function emptyFilters(): OperationFilters {
  return { operation_no: '', operation_type: null, material_name: '', dateRange: null }
}
const {
  items,
  total,
  page,
  pageSize,
  loading,
  filters,
  query,
  changePage,
  changePageSize,
  resetFilters,
} = usePagedTable<StockOperation, OperationFilters>({
  fetch: (f, pager) =>
    inventoryApi.operations({
      page: pager.page,
      page_size: pager.page_size,
      operation_no: f.operation_no.trim() || undefined,
      operation_type: f.operation_type || undefined,
      material_name: f.material_name.trim() || undefined,
      start_at: f.dateRange ? new Date(f.dateRange[0]).toISOString() : undefined,
      end_at: f.dateRange ? new Date(f.dateRange[1]).toISOString() : undefined,
    }),
  initialFilters: emptyFilters,
  onError: (error) => message.error(error instanceof Error ? error.message : '操作记录查询失败'),
  urlSync: {
    routeName: 'operations',
    fromQuery: (route) => ({
      operation_no: String(route.query.operation_no || ''),
      operation_type: String(route.query.operation_type || '') || null,
      material_name: String(route.query.material_name || ''),
      dateRange: null,
    }),
    toQuery: (f) => ({
      operation_no: f.operation_no.trim() || undefined,
      operation_type: f.operation_type || undefined,
      material_name: f.material_name.trim() || undefined,
    }),
  },
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
        <div class="filter-title">筛选条件</div>
        <div class="filter-heading-actions">
          <FilterExpandButton v-model:expanded="filterExpanded" />
        </div>
      </div>
      <div class="filter-grid">
        <label class="filter-field">
          <span>物资名称或型号规格</span>
          <n-input
            v-model:value="filters.material_name"
            clearable
            placeholder="输入物资名称或型号规格"
            @keyup.enter="query"
          />
        </label>
        <div class="filter-extras-fields" :class="{ 'filter-extras-open': filterExpanded }">
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
            <span>发生时间</span>
            <n-date-picker
              v-model:value="filters.dateRange"
              type="datetimerange"
              clearable
              class="full-width"
            />
          </label>
        </div>
      </div>
      <div class="filter-extras-actions" :class="{ 'filter-extras-open': filterExpanded }">
        <div class="filter-actions">
          <n-button @click="resetFilters">重置</n-button>
          <n-button type="primary" :loading="loading" @click="query">查询</n-button>
        </div>
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

.filter-actions {
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
