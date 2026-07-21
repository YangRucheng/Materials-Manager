<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, type DataTableColumns, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { PurchaseMaterial } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { formatDate, formatShanghaiTime } from '@/utils/time'
import { downloadBlob } from '@/utils/download'

const router = useRouter()
const message = useMessage()
const items = ref<PurchaseMaterial[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const exporting = ref(false)
const filters = reactive({ keyword: '' })

const columns: DataTableColumns<PurchaseMaterial> = [
  { title: '计划 ID', key: 'plan_no', width: 175 },
  {
    title: '需求日期',
    key: 'plan_date',
    width: 110,
    render: (row) => formatDate(row.plan_date),
  },
  {
    title: '物资名称',
    key: 'name',
    render: (row) =>
      h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: () => router.push(`/procurement/materials/${row.id}`),
        },
        { default: () => row.name },
      ),
  },
  { title: '型号规格', key: 'model_spec' },
  { title: '单位', key: 'unit_name', width: 80 },
  {
    title: '创建时间',
    key: 'created_at',
    width: 170,
    render: (row) => formatShanghaiTime(row.created_at),
  },
]

async function load() {
  loading.value = true
  try {
    const data = await procurementApi.uncodedMaterials({
      page: page.value,
      page_size: 20,
      keyword: filters.keyword || undefined,
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

async function exportExcel() {
  exporting.value = true
  try {
    const content = await procurementApi.exportUncodedMaterials({
      keyword: filters.keyword || undefined,
    })
    downloadBlob(content, '物料编码申请表.xlsx')
    message.success('物料编码申请表已导出')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">未编码物资</h1>
        <p class="page-subtitle">直接查询物料编码为空的申购计划，无单独申请单和状态流程</p>
      </div>
      <n-button :loading="exporting" :disabled="!total" @click="exportExcel">导出 Excel</n-button>
    </div>
    <n-card>
      <div class="filter-bar">
        <n-input
          v-model:value="filters.keyword"
          clearable
          placeholder="名称或型号规格"
          style="width: 260px"
          @keyup.enter="query"
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
        :row-key="(row: PurchaseMaterial) => row.id"
      />
      <div class="pagination-bar">
        <n-pagination v-model:page="page" :page-size="20" :item-count="total" @update:page="load" />
      </div>
    </n-card>
  </div>
</template>
