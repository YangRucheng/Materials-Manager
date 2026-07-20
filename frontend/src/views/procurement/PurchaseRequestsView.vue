<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, type DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { PurchaseRecord } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { requestStatusLabels, statusTagType } from '@/utils/status'
import { formatDate } from '@/utils/time'

const router = useRouter()
const items = ref<PurchaseRecord[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const filters = reactive({ keyword: '', status: null as string | null })
const columns: DataTableColumns<PurchaseRecord> = [
  {
    title: '计划日期',
    key: 'plan_date',
    width: 110,
    render: (row) => formatDate(row.plan_date),
  },
  {
    title: '申购单号',
    key: 'purchase_order_no',
    width: 170,
    render: (row) =>
      h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: () => router.push(`/procurement/records/${row.line_id}`),
        },
        { default: () => row.purchase_order_no || '未填写' },
      ),
  },
  {
    title: '追溯号',
    key: 'trace_no',
    width: 170,
    render: (row) => row.trace_no || '—',
  },
  {
    title: '物资',
    key: 'material_name',
    render: (row) =>
      h('div', [
        h('strong', row.material_name),
        h('div', { class: 'muted' }, `${row.material_code}｜${row.model_spec}`),
      ]),
  },
  { title: '申购负责人', key: 'purchase_responsible', width: 110 },
  { title: '业务员', key: 'salesperson', width: 110, render: (row) => row.salesperson || '—' },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render: (row) =>
      h(
        NTag,
        { type: statusTagType(row.status) },
        { default: () => requestStatusLabels[row.status] },
      ),
  },
  {
    title: '申购日期',
    key: 'purchase_date',
    width: 120,
    render: (row) => formatDate(row.purchase_date),
  },
  {
    title: '操作',
    key: 'action',
    width: 80,
    render: (row) =>
      h(
        NButton,
        { size: 'small', onClick: () => router.push(`/procurement/records/${row.line_id}`) },
        { default: () => '编辑' },
      ),
  },
]

async function load() {
  loading.value = true
  try {
    const data = await procurementApi.records({
      page: page.value,
      page_size: 20,
      keyword: filters.keyword || undefined,
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

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">申购记录</h1>
        <p class="page-subtitle">按物资跟踪正式申购记录、单号和到货状态</p>
      </div>
    </div>
    <n-card>
      <div class="filter-bar">
        <n-input
          v-model:value="filters.keyword"
          placeholder="申购单号、追溯号、编码、名称或业务员"
          clearable
          style="width: 300px"
        />
        <n-select
          v-model:value="filters.status"
          clearable
          :options="Object.entries(requestStatusLabels).map(([value, label]) => ({ value, label }))"
          placeholder="状态"
          style="width: 150px"
        />
        <n-button type="primary" @click="query">查询</n-button>
      </div>
    </n-card>
    <n-card>
      <n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="1325"
        :row-key="(row: PurchaseRecord) => row.line_id"
      />
      <div class="pagination-bar">
        <n-pagination v-model:page="page" :page-size="20" :item-count="total" @update:page="load" />
      </div>
    </n-card>
  </div>
</template>
