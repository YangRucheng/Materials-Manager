<script setup lang="ts">
import { h, ref, watch } from 'vue'
import { NTag, type DataTableColumns, useMessage } from 'naive-ui'
import type { PurchaseRecord } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { renderTwoLineText } from '@/utils/tableText'
import { formatDate } from '@/utils/time'

const props = defineProps<{
  show: boolean
  initialName?: string
}>()
const emit = defineEmits<{
  'update:show': [value: boolean]
}>()

const message = useMessage()
const searchName = ref('')
const searchModelSpec = ref('')
const defaultName = ref('')
const defaultModelSpec = ref('')
const items = ref<PurchaseRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)

const columns: DataTableColumns<PurchaseRecord> = [
  {
    title: '需求日期',
    key: 'plan_date',
    width: 100,
    render: (row) => formatDate(row.plan_date),
  },
  {
    title: '物资',
    key: 'material_name',
    minWidth: 200,
    render: (row) =>
      h(
        'div',
        {
          class: 'table-material-summary',
          title: `${row.material_name}\n${row.material_code || '\\'}｜${row.model_spec}`,
        },
        [
          h('div', { class: 'table-material-summary__name' }, row.material_name),
          h(
            'div',
            { class: 'table-material-summary__meta' },
            `${row.material_code || '\\'}｜${row.model_spec}`,
          ),
        ],
      ),
  },
  {
    title: '申购数量',
    key: 'purchase_qty',
    width: 100,
    render: (row) => renderTwoLineText(`${row.purchase_qty} ${row.unit_name}`),
  },
  {
    title: '申购单号',
    key: 'purchase_order_no',
    width: 130,
    render: (row) => renderTwoLineText(row.purchase_order_no, '—'),
  },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) => h(NTag, null, { default: () => row.status || '\\' }),
  },
  {
    title: '实际需求人',
    key: 'purchase_responsible',
    width: 110,
    render: (row) => renderTwoLineText(row.purchase_responsible),
  },
  {
    title: '提报员工',
    key: 'actual_demand_person',
    width: 110,
    render: (row) => renderTwoLineText(row.actual_demand_person),
  },
]

async function load() {
  loading.value = true
  try {
    const result = await procurementApi.records({
      name: searchName.value.trim() || undefined,
      model_spec: searchModelSpec.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = result.items
    total.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载历史申购记录失败')
  } finally {
    loading.value = false
  }
}

function open() {
  defaultName.value = props.initialName?.trim() || ''
  defaultModelSpec.value = ''
  restoreFilters()
  page.value = 1
  void load()
}

function restoreFilters() {
  searchName.value = defaultName.value
  searchModelSpec.value = defaultModelSpec.value
}

function search() {
  page.value = 1
  void load()
}

function clearSearch() {
  searchName.value = ''
  searchModelSpec.value = ''
  search()
}

function resetSearch() {
  restoreFilters()
  search()
}

function changePageSize(value: number) {
  pageSize.value = value
  page.value = 1
  void load()
}

watch(
  () => props.show,
  (visible) => {
    if (visible) open()
  },
)
watch(page, () => void load())
</script>

<template>
  <n-modal
    :show="props.show"
    preset="card"
    draggable
    title="历史申购记录"
    class="purchase-record-history-modal"
    style="width: min(960px, 92vw)"
    :mask-closable="false"
    :bordered="false"
    @update:show="emit('update:show', $event)"
  >
    <div class="history-search">
      <label class="filter-field">
        <span>物资名称</span>
        <n-input
          v-model:value="searchName"
          clearable
          placeholder="输入物资名称"
          @keyup.enter="search"
        />
      </label>
      <label class="filter-field">
        <span>型号</span>
        <n-input
          v-model:value="searchModelSpec"
          clearable
          placeholder="输入型号"
          @keyup.enter="search"
        />
      </label>
      <div class="history-search-actions">
        <n-button @click="clearSearch">清空</n-button>
        <n-button @click="resetSearch">重置</n-button>
        <n-button type="primary" :loading="loading" @click="search">查询</n-button>
      </div>
    </div>
    <n-data-table
      remote
      size="small"
      :bordered="false"
      :single-line="false"
      :columns="columns"
      :data="items"
      :loading="loading"
      :row-key="(row: PurchaseRecord) => row.line_id"
      :scroll-x="900"
    />
    <div class="pagination-bar">
      <n-pagination
        v-model:page="page"
        :page-size="pageSize"
        :item-count="total"
        show-size-picker
        :page-sizes="[10, 20, 50]"
        @update:page-size="changePageSize"
      />
    </div>
  </n-modal>
</template>

<style scoped>
.history-search {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-field {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 7px;
}

.filter-field > span {
  color: #4b5565;
  font-size: 13px;
  font-weight: 500;
}

.filter-field :deep(.n-input) {
  width: 100%;
  background-color: rgb(255 255 255 / 88%);
}

.history-search-actions {
  display: flex;
  gap: 10px;
}

.history-search-actions :deep(.n-button) {
  min-width: 88px;
}
</style>
