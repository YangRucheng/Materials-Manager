<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, type DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { StockOperation } from '@/api/generated'
import { inventoryApi } from '@/api/inventory'
import { formatShanghaiTime } from '@/utils/time'

const router = useRouter()
const items = ref<StockOperation[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const dateRange = ref<[number, number] | null>(null)
const filters = reactive({
  operation_no: '',
  operation_type: null as string | null,
  material_name: '',
})
const columns: DataTableColumns<StockOperation> = [
  {
    title: '流水号',
    key: 'operation_no',
    width: 150,
    render: (r) =>
      h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: () => router.push(`/warehouse/operations/${r.id}`),
        },
        { default: () => r.operation_no },
      ),
  },
  {
    title: '类型',
    key: 'operation_type',
    width: 90,
    render: (r) =>
      h(
        NTag,
        { type: r.operation_type === 'INBOUND' ? 'success' : 'warning' },
        { default: () => (r.operation_type === 'INBOUND' ? '入库' : '出库') },
      ),
  },
  {
    title: '发生时间',
    key: 'occurred_at',
    width: 170,
    render: (r) => formatShanghaiTime(r.occurred_at),
  },
  {
    title: '物资',
    key: 'lines',
    render: (r) => r.lines.map((x) => `${x.material_name} × ${x.quantity}`).join('；'),
  },
  { title: '原因', key: 'business_reason' },
  {
    title: '操作',
    key: 'action',
    width: 80,
    render: (r) =>
      h(
        NButton,
        { size: 'small', onClick: () => router.push(`/warehouse/operations/${r.id}`) },
        { default: () => '详情' },
      ),
  },
]
async function load() {
  loading.value = true
  try {
    const d = await inventoryApi.operations({
      page: page.value,
      page_size: 20,
      ...filters,
      start_at: dateRange.value?.[0],
      end_at: dateRange.value?.[1],
    })
    items.value = d.items
    total.value = d.total
  } finally {
    loading.value = false
  }
}
function query() {
  page.value = 1
  void load()
}
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">操作记录</h1>
        <p class="page-subtitle">所有库存变化均可追溯，支持授权角色修改并触发重算</p>
      </div>
    </div>
    <n-card
      ><div class="filter-bar">
        <n-input
          v-model:value="filters.operation_no"
          placeholder="流水号"
          style="width: 150px"
        /><n-select
          v-model:value="filters.operation_type"
          clearable
          :options="[
            { label: '入库', value: 'INBOUND' },
            { label: '出库', value: 'OUTBOUND' },
          ]"
          placeholder="类型"
          style="width: 110px"
        /><n-input
          v-model:value="filters.material_name"
          placeholder="物资名称"
          style="width: 150px"
        /><n-date-picker v-model:value="dateRange" type="datetimerange" clearable /><n-button
          type="primary"
          @click="query"
          >查询</n-button
        >
      </div></n-card
    ><n-card
      ><n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="1200"
        :row-key="(r: StockOperation) => r.id" />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          :page-size="20"
          :item-count="total"
          @update:page="load"
        /></div
    ></n-card>
  </div>
</template>
