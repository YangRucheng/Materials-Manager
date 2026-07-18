<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, type DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { PurchaseMaterial } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { formatShanghaiTime } from '@/utils/time'

const router = useRouter()
const items = ref<PurchaseMaterial[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const filters = reactive({ keyword: '' })

const columns: DataTableColumns<PurchaseMaterial> = [
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
    title: '关联二级库物资',
    key: 'stock_material_name',
    render: (row) => row.stock_material_name || '—',
  },
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

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">未编码物资</h1>
        <p class="page-subtitle">直接查询物料编码为空的申购计划，无单独申请单和状态流程</p>
      </div>
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
