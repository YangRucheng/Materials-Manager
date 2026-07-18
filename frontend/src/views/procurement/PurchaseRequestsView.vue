<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, type DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { PurchaseRequest } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'
import { requestStatusLabels, statusTagType } from '@/utils/status'
import { formatShanghaiTime } from '@/utils/time'

const router = useRouter()
const auth = useAuthStore()
const items = ref<PurchaseRequest[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const filters = reactive({ keyword: '', status: null as string | null })
const columns: DataTableColumns<PurchaseRequest> = [
  {
    title: '请购单号',
    key: 'request_no',
    width: 150,
    render: (r) =>
      h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: () => router.push(`/procurement/requests/${r.id}`),
        },
        { default: () => r.request_no },
      ),
  },
  { title: '申请人', key: 'applicant_name', width: 100 },
  {
    title: '明细摘要',
    key: 'lines',
    render: (r) =>
      r.lines.map((x) => `${x.material_name_snapshot} × ${x.requested_qty}`).join('；'),
  },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render: (r) =>
      h(NTag, { type: statusTagType(r.status) }, { default: () => requestStatusLabels[r.status] }),
  },
  { title: '受理人', key: 'handler_name', width: 100, render: (r) => r.handler_name || '—' },
  {
    title: '创建时间',
    key: 'created_at',
    width: 170,
    render: (r) => formatShanghaiTime(r.created_at),
  },
  {
    title: '操作',
    key: 'action',
    width: 80,
    render: (r) =>
      h(
        NButton,
        { size: 'small', onClick: () => router.push(`/procurement/requests/${r.id}`) },
        { default: () => '详情' },
      ),
  },
]
async function load() {
  loading.value = true
  try {
    const d = await procurementApi.requests({ page: page.value, page_size: 20, ...filters })
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
        <h1 class="page-title">请购单</h1>
        <p class="page-subtitle">从草稿、受理到到货入库的闭环跟踪</p>
      </div>
      <n-button
        v-if="auth.can('purchase:write')"
        type="primary"
        @click="router.push('/procurement/requests/new')"
        >新建请购</n-button
      >
    </div>
    <n-card
      ><div class="filter-bar">
        <n-input
          v-model:value="filters.keyword"
          placeholder="请购单号、物资名称"
          clearable
          style="width: 240px"
        /><n-select
          v-model:value="filters.status"
          clearable
          :options="Object.entries(requestStatusLabels).map(([value, label]) => ({ value, label }))"
          placeholder="状态"
          style="width: 150px"
        /><n-button type="primary" @click="query">查询</n-button>
      </div></n-card
    ><n-card
      ><n-data-table
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="1050"
        :row-key="(r: PurchaseRequest) => r.id" />
      <div class="text-right">
        <n-pagination
          v-model:page="page"
          :page-size="20"
          :item-count="total"
          @update:page="load"
        /></div
    ></n-card>
  </div>
</template>
