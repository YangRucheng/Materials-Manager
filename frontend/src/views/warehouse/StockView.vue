<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useMessage, type DataTableColumns } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { inventoryApi } from '@/api/inventory'
import type { InventoryBalance, ReplenishmentDraftWrite } from '@/api/generated'
import { useAuthStore } from '@/stores/auth'
import { formatShanghaiTime } from '@/utils/time'
import { isDecimalString } from '@/utils/decimal'
import QuantityInput from '@/components/QuantityInput.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const loading = ref(false)
const items = ref<InventoryBalance[]>([])
const total = ref(0)
const page = ref(1)
const showReplenishment = ref(false)
const replenishing = ref(false)
const replenishmentRow = ref<InventoryBalance | null>(null)
const replenishmentForm = reactive<ReplenishmentDraftWrite>({
  planned_qty: '',
  actual_demand_person: '',
  purchase_responsible: '',
})
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
    key: 'is_low_stock',
    width: 140,
    render: (r) =>
      r.is_low_stock
        ? h(NTag, { type: 'error', size: 'small' }, { default: () => '低库存' })
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
                  disabled: !r.is_low_stock || r.suggested_purchase_qty === '0',
                  onClick: () => openReplenishment(r),
                },
                { default: () => '发起补库' },
              ),
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
                  type: 'primary',
                  onClick: () =>
                    router.push({ name: 'outbound', query: { material_id: r.stock_material_id } }),
                },
                { default: () => '出库' },
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
function openReplenishment(row: InventoryBalance) {
  replenishmentRow.value = row
  Object.assign(replenishmentForm, {
    planned_qty: row.suggested_purchase_qty,
    actual_demand_person: '',
    purchase_responsible: '',
  })
  showReplenishment.value = true
}
async function confirmReplenishment() {
  const row = replenishmentRow.value
  if (!row) return
  if (
    !isDecimalString(replenishmentForm.planned_qty, row.decimal_places) ||
    !replenishmentForm.actual_demand_person.trim() ||
    !replenishmentForm.purchase_responsible.trim()
  ) {
    message.error('请确认计划数量、实际需求人和申购负责人')
    return
  }
  replenishing.value = true
  try {
    const result = await inventoryApi.replenish(row.stock_material_id, {
      planned_qty: replenishmentForm.planned_qty,
      actual_demand_person: replenishmentForm.actual_demand_person.trim(),
      purchase_responsible: replenishmentForm.purchase_responsible.trim(),
    })
    message.success('已添加一条申购计划')
    showReplenishment.value = false
    await router.push(`/procurement/materials/${result.resource_id}`)
  } catch (e) {
    message.error(e instanceof Error ? e.message : '发起失败')
  } finally {
    replenishing.value = false
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
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="900"
        :row-key="(r: InventoryBalance) => r.stock_material_id" />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          :item-count="total"
          :page-size="20"
          @update:page="load"
        /></div
    ></n-card>
    <n-modal
      v-model:show="showReplenishment"
      preset="card"
      title="确认发起补库"
      style="width: 560px"
      :mask-closable="false"
    >
      <n-alert type="warning" style="margin-bottom: 16px">
        确认以下信息后才会新增申购计划，取消不会产生任何数据。
      </n-alert>
      <n-descriptions v-if="replenishmentRow" :column="2" label-placement="left">
        <n-descriptions-item label="物资">{{ replenishmentRow.name }}</n-descriptions-item>
        <n-descriptions-item label="型号规格">{{
          replenishmentRow.model_spec
        }}</n-descriptions-item>
        <n-descriptions-item label="当前库存"
          >{{ replenishmentRow.current_qty }} {{ replenishmentRow.unit_name }}</n-descriptions-item
        >
        <n-descriptions-item label="建议申购"
          >{{ replenishmentRow.suggested_purchase_qty }}
          {{ replenishmentRow.unit_name }}</n-descriptions-item
        >
      </n-descriptions>
      <n-divider />
      <n-form label-placement="top">
        <n-form-item label="计划数量" required>
          <QuantityInput
            v-model:value="replenishmentForm.planned_qty"
            :decimal-places="replenishmentRow?.decimal_places ?? 1"
          />
        </n-form-item>
        <div class="form-grid">
          <n-form-item label="实际需求人" required>
            <n-input
              v-model:value="replenishmentForm.actual_demand_person"
              maxlength="128"
              placeholder="填写提出实际需求的员工"
            />
          </n-form-item>
          <n-form-item label="申购负责人" required>
            <n-input
              v-model:value="replenishmentForm.purchase_responsible"
              maxlength="128"
              placeholder="填写负责申购的人员"
            />
          </n-form-item>
        </div>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showReplenishment = false">取消</n-button>
          <n-button type="primary" :loading="replenishing" @click="confirmReplenishment"
            >确认并新增计划</n-button
          >
        </n-space>
      </template>
    </n-modal>
  </div>
</template>
