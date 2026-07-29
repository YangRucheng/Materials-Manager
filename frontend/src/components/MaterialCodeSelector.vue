<script setup lang="ts">
import { h, ref, watch } from 'vue'
import { NButton, type DataTableColumns, useMessage } from 'naive-ui'
import type { MaterialCodeLibrary } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { renderTwoLineText } from '@/utils/tableText'

defineProps<{
  modelValue: string
  disabled?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
  select: [item: MaterialCodeLibrary]
}>()

const message = useMessage()
const show = ref(false)
const materialCode = ref('')
const name = ref('')
const modelSpec = ref('')
const items = ref<MaterialCodeLibrary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)

const columns: DataTableColumns<MaterialCodeLibrary> = [
  { title: '物料编码', key: 'material_code', width: 150 },
  {
    title: '名称',
    key: 'name',
    minWidth: 180,
    render: (row) => renderTwoLineText(row.name, '—'),
  },
  {
    title: '型号',
    key: 'model_spec',
    minWidth: 220,
    render: (row) => renderTwoLineText(row.model_spec, '—'),
  },
  { title: '计量单位', key: 'unit_name', width: 100 },
  {
    title: '操作',
    key: 'actions',
    width: 88,
    render: (row) =>
      h(
        NButton,
        { type: 'primary', size: 'small', secondary: true, onClick: () => selectItem(row) },
        { default: () => '采用' },
      ),
  },
]

async function load() {
  loading.value = true
  try {
    const result = await procurementApi.materialCodes({
      material_code: materialCode.value.trim() || undefined,
      name: name.value.trim() || undefined,
      model_spec: modelSpec.value.trim() || undefined,
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

function open() {
  materialCode.value = ''
  name.value = ''
  modelSpec.value = ''
  page.value = 1
  show.value = true
  void load()
}

function search() {
  page.value = 1
  void load()
}

function resetSearch() {
  materialCode.value = ''
  name.value = ''
  modelSpec.value = ''
  search()
}

function changePageSize(value: number) {
  pageSize.value = value
  page.value = 1
  void load()
}

function selectItem(item: MaterialCodeLibrary) {
  emit('update:modelValue', item.material_code)
  emit('select', item)
  show.value = false
}

watch(page, () => void load())
</script>

<template>
  <n-input
    :value="modelValue"
    :disabled="disabled"
    maxlength="64"
    placeholder="可直接输入编码"
    @update:value="emit('update:modelValue', $event)"
  >
    <template #suffix>
      <n-button text type="primary" size="tiny" :disabled="disabled" @click.stop="open">
        选择编码
      </n-button>
    </template>
  </n-input>
  <n-modal
    v-model:show="show"
    preset="card"
    draggable
    title="选择物料编码"
    class="material-code-selector-modal"
    style="width: min(960px, 92vw)"
    :mask-closable="false"
    :bordered="false"
  >
    <div class="selector-search">
      <div class="selector-search-fields">
        <n-input
          v-model:value="modelSpec"
          clearable
          placeholder="按型号搜索"
          @keyup.enter="search"
        />
        <n-input v-model:value="name" clearable placeholder="按名称搜索" @keyup.enter="search" />
        <n-input
          v-model:value="materialCode"
          clearable
          placeholder="按编码搜索"
          @keyup.enter="search"
        />
      </div>
      <div class="selector-search-actions">
        <n-button type="primary" :loading="loading" @click="search">搜索</n-button>
        <n-button @click="resetSearch">重置</n-button>
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
      :row-key="(row: MaterialCodeLibrary) => row.id"
      :scroll-x="760"
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
.selector-search {
  padding: 14px;
  margin-bottom: 16px;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-control);
  background: linear-gradient(145deg, var(--color-surface) 0%, var(--color-surface-soft) 100%);
}

.selector-search-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.selector-search-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

@media (max-width: 680px) {
  .selector-search-fields {
    grid-template-columns: 1fr;
  }
}
</style>
