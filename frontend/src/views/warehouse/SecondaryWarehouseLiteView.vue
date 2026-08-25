<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import { useDialog, useMessage } from 'naive-ui'
import type { LiteInventory } from '@/api/generated'
import { secondaryWarehouseApi } from '@/api/secondaryWarehouse'
import { useAuthStore } from '@/stores/auth'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import { useImportJob } from '@/composables/useImportJob'
import { usePagedTable } from '@/composables/usePagedTable'
import { formatShanghaiTime } from '@/utils/time'

const auth = useAuthStore()
const dialog = useDialog()
const message = useMessage()
const fileInput = ref<HTMLInputElement | null>(null)
type LiteFilters = {
  keyword: string
}
const {
  items,
  total,
  page,
  pageSize,
  loading,
  filters,
  query,
  changePage,
  changePageSize,
  resetFilters,
} = usePagedTable<LiteInventory, LiteFilters>({
  fetch: (f, pager) =>
    secondaryWarehouseApi.list({
      keyword: f.keyword.trim() || undefined,
      page: pager.page,
      page_size: pager.page_size,
    }),
  initialFilters: () => ({ keyword: '' }),
  onError: (error) => message.error(error instanceof Error ? error.message : '加载二级库失败'),
  pageSizeOptions: [20, 50, 100, 200],
})
const importJob = useImportJob({
  start: (file) => secondaryWarehouseApi.import(file),
  poll: (jobId) => secondaryWarehouseApi.importJob(jobId),
})
const importing = computed(() => importJob.running.value)
const lastImportAt = ref('')
async function loadLastImport() {
  try {
    const result = await secondaryWarehouseApi.lastImport()
    lastImportAt.value = formatShanghaiTime(result.last_import_at ?? undefined)
  } catch {
    lastImportAt.value = '—'
  }
}
onMounted(() => void loadLastImport())
const activeFilterCount = computed(() => [filters.keyword.trim()].filter(Boolean).length)

const columns: DataTableColumns<LiteInventory> = preventTableColumnCompression([
  {
    title: '物资名称',
    key: 'name',
    width: tableColumnWidths.name,
    ellipsis: { tooltip: true },
    render: (row) => h('strong', row.name),
  },
  {
    title: '型号规格',
    key: 'model_spec',
    width: tableColumnWidths.model,
    ellipsis: { tooltip: true },
    render: (row) => row.model_spec || '—',
  },
  {
    title: '单位',
    key: 'unit_name',
    width: tableColumnWidths.unit,
    render: (row) => row.unit_name || '—',
  },
  {
    title: '数量',
    key: 'quantity',
    width: tableColumnWidths.quantity,
    align: 'right',
    render: (row) => row.quantity ?? '—',
  },
  {
    title: '备注',
    key: 'remark',
    width: tableColumnWidths.text,
    ellipsis: { tooltip: true },
    render: (row) => row.remark || '—',
  },
])
const tableScrollX = getTableScrollX(columns)

function openFilePicker() {
  fileInput.value?.click()
}

function showImportSummary(result: Record<string, unknown> | null) {
  const importedCount = Number(result?.imported_count ?? 0)
  dialog.success({
    draggable: true,
    title: '导入完成',
    content: `已全量更新 ${importedCount.toLocaleString()} 条二级库数据。`,
    positiveText: '知道了',
    positiveButtonProps: { type: 'primary' },
  })
}

async function importFile(file: File) {
  try {
    const result = await importJob.run(file)
    showImportSummary(result)
    filters.keyword = ''
    page.value = 1
    await query()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导入失败')
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  dialog.warning({
    draggable: true,
    title: '全量更新二级库',
    content: `确认导入“${file.name}”吗？现有精简版二级库数据将被全部删除，并由该文件完整替换。`,
    positiveText: '确认全量更新',
    negativeText: '取消',
    positiveButtonProps: { type: 'primary' },
    onPositiveClick: () => importFile(file),
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">二级库</h1>
      <n-button
        v-if="auth.can('warehouse:write')"
        type="primary"
        :loading="importing"
        @click="openFilePicker"
      >
        导入表格全量更新
      </n-button>
      <input
        ref="fileInput"
        class="hidden-file-input"
        type="file"
        accept=".xls,.xlsx,.xlsm,.csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
        @change="onFileChange"
      />
    </div>

    <n-card class="filter-card" :bordered="false">
      <div class="filter-heading">
        <div class="filter-title">筛选条件</div>
        <n-tag v-if="activeFilterCount" :bordered="false" round type="success">
          已启用 {{ activeFilterCount }} 项
        </n-tag>
      </div>
      <div class="filter-grid">
        <label class="filter-field">
          <span>物资名称 / 型号 / 备注</span>
          <n-input
            v-model:value="filters.keyword"
            clearable
            placeholder="输入名称、型号或备注"
            @keyup.enter="query"
          />
        </label>
      </div>
      <div class="filter-actions">
        <span class="muted"
          >共 {{ total.toLocaleString() }} 条 · 上次导入：{{ lastImportAt || '—' }}</span
        >
        <div class="filter-action-buttons">
          <n-button @click="resetFilters">重置</n-button>
          <n-button type="primary" :loading="loading" @click="query">查询</n-button>
        </div>
      </div>
    </n-card>

    <n-card class="data-card">
      <n-data-table
        remote
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: LiteInventory) => row.id"
        :scroll-x="tableScrollX"
      />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :item-count="total"
          show-size-picker
          :page-sizes="[20, 50, 100, 200]"
          @update:page="changePage"
          @update:page-size="changePageSize"
        />
      </div>
    </n-card>
  </div>
</template>

<style scoped>
.hidden-file-input {
  display: none;
}

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

.filter-actions {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #edf1f6;
}

.filter-action-buttons {
  display: flex;
  flex: none;
  gap: 10px;
}

.filter-action-buttons :deep(.n-button) {
  min-width: 88px;
}

@media (max-width: 760px) {
  .filter-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .filter-action-buttons {
    justify-content: flex-end;
  }
}
</style>
