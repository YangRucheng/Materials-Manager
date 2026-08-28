<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import { useDialog, useMessage } from 'naive-ui'
import type { MaterialCodeLibrary } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import { useImportJob } from '@/composables/useImportJob'
import { usePagedTable } from '@/composables/usePagedTable'
import { formatShanghaiTime } from '@/utils/time'
import FilterExpandButton from '@/components/FilterExpandButton.vue'

const auth = useAuthStore()
const dialog = useDialog()
const message = useMessage()
const fileInput = ref<HTMLInputElement | null>(null)
const filterExpanded = ref(false)
type CodeLibraryFilters = {
  materialCode: string
  name: string
  modelSpec: string
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
} = usePagedTable<MaterialCodeLibrary, CodeLibraryFilters>({
  fetch: (f, pager) =>
    procurementApi.materialCodes({
      material_code: f.materialCode.trim() || undefined,
      name: f.name.trim() || undefined,
      model_spec: f.modelSpec.trim() || undefined,
      page: pager.page,
      page_size: pager.page_size,
    }),
  initialFilters: () => ({ materialCode: '', name: '', modelSpec: '' }),
  onError: (error) => message.error(error instanceof Error ? error.message : '加载物料编码库失败'),
  pageSizeOptions: [20, 50, 100, 200],
})
const importJob = useImportJob({
  start: (file) => procurementApi.importMaterialCodes(file),
  poll: (jobId) => procurementApi.materialCodeImportJob(jobId),
})
const importing = computed(() => importJob.running.value)
const lastImportAt = ref('')
async function loadLastImport() {
  try {
    const result = await procurementApi.materialCodeLastImport()
    lastImportAt.value = formatShanghaiTime(result.last_import_at ?? undefined)
  } catch {
    lastImportAt.value = '—'
  }
}
onMounted(() => void loadLastImport())
const activeFilterCount = computed(
  () =>
    [filters.name.trim(), filters.modelSpec.trim(), filters.materialCode.trim()].filter(Boolean)
      .length,
)

const columns: DataTableColumns<MaterialCodeLibrary> = preventTableColumnCompression([
  {
    title: '物料编码',
    key: 'material_code',
    width: tableColumnWidths.code,
    render: (row) => h('strong', row.material_code),
  },
  {
    title: '名称',
    key: 'name',
    width: tableColumnWidths.name,
    ellipsis: { tooltip: true },
    render: (row) => row.name || '—',
  },
  {
    title: '型号',
    key: 'model_spec',
    width: tableColumnWidths.model,
    ellipsis: { tooltip: true },
    render: (row) => row.model_spec || '—',
  },
  { title: '计量单位', key: 'unit_name', width: tableColumnWidths.unit },
])
const tableScrollX = getTableScrollX(columns)

function openFilePicker() {
  fileInput.value?.click()
}

function showImportSummary(result: Record<string, unknown> | null) {
  const importedCount = Number(result?.imported_count ?? 0)
  const blankNameCount = Number(result?.blank_name_count ?? 0)
  const blankModelCount = Number(result?.blank_model_spec_count ?? 0)
  const notes = [
    `已全量更新 ${importedCount.toLocaleString()} 条物料编码。`,
    blankNameCount ? `${blankNameCount.toLocaleString()} 条名称为空。` : '',
    blankModelCount ? `${blankModelCount.toLocaleString()} 条型号为空。` : '',
  ].filter(Boolean)
  dialog.success({
    draggable: true,
    title: '导入完成',
    content: notes.join('\n'),
    positiveText: '知道了',
    positiveButtonProps: { type: 'primary' },
  })
}

async function importFile(file: File) {
  try {
    const result = await importJob.run(file)
    showImportSummary(result)
    filters.materialCode = ''
    filters.name = ''
    filters.modelSpec = ''
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
    title: '全量更新物料编码库',
    content: `确认导入“${file.name}”吗？现有编码库将被全部删除，并由该文件完整替换。`,
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
      <h1 class="page-title">物料编码库</h1>
      <n-button
        v-if="auth.can('purchase:write')"
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
        <div class="filter-heading-actions">
          <n-tag v-if="activeFilterCount" :bordered="false" round type="success">
            已启用 {{ activeFilterCount }} 项
          </n-tag>
          <FilterExpandButton v-model:expanded="filterExpanded" />
        </div>
      </div>
      <div class="filter-grid">
        <label class="filter-field">
          <span>物资名称</span>
          <n-input
            v-model:value="filters.name"
            clearable
            placeholder="输入物资名称"
            @keyup.enter="query"
          />
        </label>
        <label class="filter-field">
          <span>型号规格</span>
          <n-input
            v-model:value="filters.modelSpec"
            clearable
            placeholder="输入型号规格"
            @keyup.enter="query"
          />
        </label>
        <div class="filter-extras-fields" :class="{ 'filter-extras-open': filterExpanded }">
          <label class="filter-field">
            <span>物料编码</span>
            <n-input
              v-model:value="filters.materialCode"
              clearable
              placeholder="输入物料编码"
              @keyup.enter="query"
            />
          </label>
        </div>
      </div>
      <div class="filter-extras-actions" :class="{ 'filter-extras-open': filterExpanded }">
        <div class="filter-actions">
          <span class="muted"
            >共 {{ total.toLocaleString() }} 条 · 上次导入：{{ lastImportAt || '—' }}</span
          >
          <div class="filter-action-buttons">
            <n-button @click="resetFilters">重置</n-button>
            <n-button type="primary" :loading="loading" @click="query">查询</n-button>
          </div>
        </div>
      </div>
    </n-card>

    <n-card class="data-card">
      <n-data-table
        remote
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: MaterialCodeLibrary) => row.id"
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
