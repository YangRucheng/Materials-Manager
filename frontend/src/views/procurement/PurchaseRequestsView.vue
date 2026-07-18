<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, type DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { PurchaseRecord } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { requestStatusLabels, statusTagType } from '@/utils/status'
import { formatShanghaiTime } from '@/utils/time'

const router = useRouter()
const items = ref<PurchaseRecord[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const filters = reactive({ keyword: '', status: null as string | null })
const columns: DataTableColumns<PurchaseRecord> = [
  {
    title: '申购记录号',
    key: 'request_no',
    width: 170,
    render: (row) =>
      h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: () => router.push(`/procurement/records/${row.line_id}`),
        },
        { default: () => row.request_no },
      ),
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
  {
    title: '计划 / 已到 / 未到',
    key: 'quantity',
    width: 190,
    render: (row) =>
      `${row.planned_qty} / ${row.received_qty} / ${row.remaining_qty} ${row.unit_name}`,
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
    title: '提交时间',
    key: 'submitted_at',
    width: 170,
    render: (row) => formatShanghaiTime(row.submitted_at),
  },
  {
    title: '操作',
    key: 'action',
    width: 80,
    render: (row) =>
      h(
        NButton,
        { size: 'small', onClick: () => router.push(`/procurement/records/${row.line_id}`) },
        { default: () => '跟踪' },
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
        <p class="page-subtitle">按物资展平跟踪正式申购的计划量、到货量和未到数量</p>
      </div>
    </div>
    <n-card>
      <div class="filter-bar">
        <n-input
          v-model:value="filters.keyword"
          placeholder="记录号、编码、名称、业务员或备注"
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
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="1200"
        :row-key="(row: PurchaseRecord) => row.line_id"
      />
      <div class="text-right">
        <n-pagination v-model:page="page" :page-size="20" :item-count="total" @update:page="load" />
      </div>
    </n-card>
  </div>
</template>
