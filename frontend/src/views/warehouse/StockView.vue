<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useMessage, type DataTableColumns } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { inventoryApi } from '@/api/inventory'
import type { InventoryBalance } from '@/api/generated'
import { useAuthStore } from '@/stores/auth'
import { formatShanghaiTime } from '@/utils/time'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const loading = ref(false)
const items = ref<InventoryBalance[]>([])
const total = ref(0)
const page = ref(1)
const filters = reactive({
  keyword: '',
  low_stock: route.query.low_stock === 'true' ? true : (null as boolean | null),
  min_qty: '',
  max_qty: '',
})
const columns: DataTableColumns<InventoryBalance> = [
  {
    title: '物资名称',
    key: 'name',
    render: (r) => h('div', [h('strong', r.name), h('div', { class: 'muted' }, r.model_spec)]),
  },
  { title: '单位', key: 'unit_name', width: 70 },
  { title: '当前库存', key: 'current_qty', width: 100 },
  {
    title: '预警状态',
    key: 'warning_state',
    width: 140,
    render: (r) =>
      r.is_low_stock
        ? h(
            NTag,
            { type: r.warning_state === 'ON_ORDER' ? 'info' : 'error', size: 'small' },
            { default: () => (r.warning_state === 'ON_ORDER' ? '已申购待入库' : '待申购') },
          )
        : h(NTag, { size: 'small' }, { default: () => '正常' }),
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 170,
    render: (r) => formatShanghaiTime(r.updated_at),
  },
  {
    title: '操作',
    key: 'actions',
    width: 300,
    render: (r) =>
      h('div', { class: 'action-row' }, [
        h(
          NButton,
          {
            size: 'small',
            onClick: () => router.push(`/warehouse/materials/${r.stock_material_id}`),
          },
          { default: () => '详情' },
        ),
        ...(auth.can('warehouse:write')
          ? [
              h(
                NButton,
                {
                  size: 'small',
                  onClick: () =>
                    router.push({
                      name: 'inbound',
                      query: { material_id: r.stock_material_id },
                    }),
                },
                { default: () => '入库' },
              ),
              h(
                NButton,
                {
                  size: 'small',
                  onClick: () =>
                    router.push({ name: 'outbound', query: { material_id: r.stock_material_id } }),
                },
                { default: () => '出库' },
              ),
              h(
                NButton,
                {
                  size: 'small',
                  type: 'primary',
                  disabled: !r.is_low_stock || r.suggested_purchase_qty === '0',
                  onClick: () => replenish(r),
                },
                { default: () => '发起补库' },
              ),
            ]
          : []),
      ]),
  },
]
async function load() {
  loading.value = true
  try {
    const api = filters.low_stock ? inventoryApi.lowStock : inventoryApi.balances
    const data = await api({
      page: page.value,
      page_size: 20,
      keyword: filters.keyword || undefined,
      min_qty: filters.min_qty || undefined,
      max_qty: filters.max_qty || undefined,
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
async function replenish(row: InventoryBalance) {
  try {
    const result = await inventoryApi.replenish(row.stock_material_id)
    message.success('已添加一条申购计划')
    await router.push(`/procurement/materials/${result.resource_id}`)
  } catch (e) {
    message.error(e instanceof Error ? e.message : '发起失败')
  }
}
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">库存查询</h1>
        <p class="page-subtitle">余额只由入库、出库流水计算，不提供直接调整入口</p>
      </div>
    </div>
    <n-card
      ><div class="filter-bar">
        <n-input
          v-model:value="filters.keyword"
          clearable
          placeholder="名称或型号"
          style="width: 220px"
        /><n-input
          v-model:value="filters.min_qty"
          placeholder="库存下限"
          style="width: 120px"
        /><n-input
          v-model:value="filters.max_qty"
          placeholder="库存上限"
          style="width: 120px"
        /><n-select
          v-model:value="filters.low_stock"
          clearable
          :options="[
            { label: '仅低库存', value: true },
            { label: '全部库存', value: false },
          ]"
          style="width: 140px"
        /><n-button type="primary" @click="query">查询</n-button>
      </div></n-card
    >
    <n-card
      ><n-data-table
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="900"
        :row-key="(r: InventoryBalance) => r.stock_material_id" />
      <div class="text-right">
        <n-pagination
          v-model:page="page"
          :item-count="total"
          :page-size="20"
          @update:page="load"
        /></div
    ></n-card>
  </div>
</template>
