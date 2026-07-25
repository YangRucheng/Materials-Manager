<script setup lang="ts">
import { h, onMounted, ref, watch } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import { useDialog, useMessage } from 'naive-ui'
import type { MaterialCodeLibrary, MaterialCodeLibraryImportResult } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const dialog = useDialog()
const message = useMessage()
const fileInput = ref<HTMLInputElement | null>(null)
const items = ref<MaterialCodeLibrary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const loading = ref(false)
const importing = ref(false)

const columns: DataTableColumns<MaterialCodeLibrary> = [
  {
    title: '物料编码',
    key: 'material_code',
    width: 170,
    render: (row) => h('strong', row.material_code),
  },
  {
    title: '名称',
    key: 'name',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => row.name || '—',
  },
  {
    title: '型号',
    key: 'model_spec',
    minWidth: 260,
    ellipsis: { tooltip: true },
    render: (row) => row.model_spec || '—',
  },
  { title: '计量单位', key: 'unit_name', width: 120 },
]

async function load() {
  loading.value = true
  try {
    const result = await procurementApi.materialCodes({
      keyword: keyword.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = result.items
    total.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载物料编码库失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function resetSearch() {
  keyword.value = ''
  search()
}

function changePageSize(value: number) {
  pageSize.value = value
  page.value = 1
  void load()
}

function openFilePicker() {
  fileInput.value?.click()
}

function showImportSummary(result: MaterialCodeLibraryImportResult) {
  const notes = [
    `已全量更新 ${result.imported_count.toLocaleString()} 条物料编码。`,
    result.blank_name_count ? `${result.blank_name_count.toLocaleString()} 条名称为空。` : '',
    result.blank_model_spec_count
      ? `${result.blank_model_spec_count.toLocaleString()} 条型号为空。`
      : '',
  ].filter(Boolean)
  if (result.unmatched_unit_names.length) {
    notes.push(`以下计量单位尚未在系统配置：${result.unmatched_unit_names.join('、')}`)
  }
  dialog.success({ title: '导入完成', content: notes.join('\n'), positiveText: '知道了' })
}

async function importFile(file: File) {
  importing.value = true
  try {
    const result = await procurementApi.importMaterialCodes(file)
    showImportSummary(result)
    keyword.value = ''
    page.value = 1
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导入失败')
  } finally {
    importing.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  dialog.warning({
    title: '全量更新物料编码库',
    content: `确认导入“${file.name}”吗？现有编码库将被全部删除，并由该文件完整替换。`,
    positiveText: '确认全量更新',
    negativeText: '取消',
    onPositiveClick: () => importFile(file),
  })
}

watch(page, () => void load())
onMounted(() => void load())
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
        导入 Excel 全量更新
      </n-button>
      <input
        ref="fileInput"
        class="hidden-file-input"
        type="file"
        accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        @change="onFileChange"
      />
    </div>

    <n-card class="filter-card">
      <div class="filter-bar">
        <n-input
          v-model:value="keyword"
          clearable
          style="width: min(460px, 100%)"
          placeholder="按名称、型号或物料编码搜索"
          @keyup.enter="search"
        />
        <n-button type="primary" :loading="loading" @click="search">搜索</n-button>
        <n-button @click="resetSearch">重置</n-button>
        <span class="muted">共 {{ total.toLocaleString() }} 条</span>
      </div>
    </n-card>

    <n-card class="data-card">
      <n-data-table
        remote
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: MaterialCodeLibrary) => row.id"
        :scroll-x="780"
      />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          :page-size="pageSize"
          :item-count="total"
          show-size-picker
          :page-sizes="[20, 50, 100, 200]"
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
</style>
