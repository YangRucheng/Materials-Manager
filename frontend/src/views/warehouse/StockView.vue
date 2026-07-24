<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { inventoryApi } from '@/api/inventory'
import type { InventoryBalance, ReplenishmentDraftWrite } from '@/api/generated'
import { useAuthStore } from '@/stores/auth'
import { formatShanghaiTime, toShanghaiDate } from '@/utils/time'
import { isDecimalString } from '@/utils/decimal'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'
import QuantityInput from '@/components/QuantityInput.vue'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const rowClickGuard = createTableRowClickGuard()
const loading = ref(false)
const items = ref<InventoryBalance[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const showReplenishment = ref(false)
const replenishing = ref(false)
const loadingDefaults = ref(false)
const replenishmentRow = ref<InventoryBalance | null>(null)
const replenishmentForm = reactive<ReplenishmentDraftWrite>({
  planned_qty: '',
  demand_date: toShanghaiDate(Date.now()),
  actual_demand_person: '',
  purchase_responsible: '',
})
const filters = reactive({
  keyword: '',
  low_stock: route.query.low_stock === 'true' ? true : (null as boolean | null),
  min_qty: '',
  max_qty: '',
})
const columns = preventTableColumnCompression<InventoryBalance>([
  {
    title: '物资名称',
    key: 'name',
    width: tableColumnWidths.material,
    render: (r) => h('div', [h('strong', r.name), h('div', { class: 'muted' }, r.model_spec)]),
  },
  { title: '计量单位', key: 'unit_name', width: tableColumnWidths.unit },
  { title: '当前库存', key: 'current_qty', width: tableColumnWidths.quantity },
  {
    title: '预警状态',
    key: 'is_low_stock',
    width: tableColumnWidths.status,
    render: (r) =>
      r.is_low_stock
        ? h(NTag, { type: 'error', size: 'small' }, { default: () => '低库存' })
        : h(NTag, { size: 'small' }, { default: () => '正常' }),
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: tableColumnWidths.datetime,
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
                  disabled: !r.is_low_stock,
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
])
const tableScrollX = getTableScrollX(columns)
async function load() {
  loading.value = true
  try {
    const api = filters.low_stock ? inventoryApi.lowStock : inventoryApi.balances
    const data = await api({
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword || undefined,
      min_qty: filters.min_qty || undefined,
      max_qty: filters.max_qty || undefined,
    })
    items.value = data.items
    total.value = data.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : '库存查询失败')
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
  Object.assign(filters, { keyword: '', low_stock: null, min_qty: '', max_qty: '' })
  query()
}
function rowProps(row: InventoryBalance) {
  return {
    style: 'cursor: pointer',
    onMousedown: rowClickGuard.onMouseDown,
    onClick: (event: MouseEvent) => {
      if (!rowClickGuard.shouldIgnore(event)) {
        void router.push({
          name: 'stock-material-detail',
          params: { id: row.stock_material_id },
        })
      }
    },
  }
}
async function openReplenishment(row: InventoryBalance) {
  replenishmentRow.value = row
  Object.assign(replenishmentForm, {
    planned_qty: row.suggested_purchase_qty === '0' ? '' : row.suggested_purchase_qty,
    demand_date: toShanghaiDate(Date.now()),
    actual_demand_person: '',
    purchase_responsible: '',
  })
  showReplenishment.value = true
  loadingDefaults.value = true
  try {
    const defaults = await inventoryApi.replenishmentDefaults()
    if (replenishmentRow.value?.stock_material_id === row.stock_material_id) {
      replenishmentForm.demand_date = defaults.demand_date
      replenishmentForm.purchase_responsible = defaults.purchase_responsible
    }
  } catch {
    message.warning('默认申购负责人加载失败，请手动填写')
  } finally {
    loadingDefaults.value = false
  }
}
async function confirmReplenishment() {
  const row = replenishmentRow.value
  if (!row) return
  if (
    !isDecimalString(replenishmentForm.planned_qty, row.decimal_places) ||
    !replenishmentForm.demand_date ||
    !replenishmentForm.actual_demand_person.trim() ||
    !replenishmentForm.purchase_responsible.trim()
  ) {
    message.error('请确认需求日期、计划数量、实际需求人和申购负责人')
    return
  }
  replenishing.value = true
  try {
    const result = await inventoryApi.replenish(row.stock_material_id, {
      planned_qty: replenishmentForm.planned_qty,
      demand_date: replenishmentForm.demand_date,
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
          <span>名称或型号规格</span>
          <n-input
            v-model:value="filters.keyword"
            clearable
            placeholder="输入物资名称或型号规格"
            @keyup.enter="query"
          />
        </label>
        <label class="filter-field">
          <span>库存下限</span>
          <n-input v-model:value="filters.min_qty" clearable placeholder="输入库存下限" />
        </label>
        <label class="filter-field">
          <span>库存上限</span>
          <n-input v-model:value="filters.max_qty" clearable placeholder="输入库存上限" />
        </label>
        <label class="filter-field">
          <span>预警状态</span>
          <n-select
            v-model:value="filters.low_stock"
            clearable
            :options="[
              { label: '仅低库存', value: true },
              { label: '全部库存', value: false },
            ]"
            placeholder="选择预警状态"
          />
        </label>
      </div>
      <div class="filter-actions">
        <n-button @click="resetFilters">重置</n-button>
        <n-button type="primary" :loading="loading" @click="query">查询</n-button>
      </div>
    </n-card>
    <n-card class="data-card" :bordered="false"
      ><n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-props="rowProps"
        :scroll-x="tableScrollX"
        :row-key="(r: InventoryBalance) => r.stock_material_id" />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :item-count="total"
          :page-sizes="[10, 20, 50, 100, 200]"
          show-size-picker
          @update:page="changePage"
          @update:page-size="changePageSize"
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
        <div class="form-grid">
          <n-form-item label="需求日期" required>
            <n-date-picker
              v-model:formatted-value="replenishmentForm.demand_date"
              type="date"
              value-format="yyyy-MM-dd"
              :disabled="loadingDefaults"
              class="full-width"
            />
          </n-form-item>
          <n-form-item label="计划数量" required>
            <QuantityInput
              v-model:value="replenishmentForm.planned_qty"
              :decimal-places="replenishmentRow?.decimal_places ?? 1"
            />
          </n-form-item>
        </div>
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
