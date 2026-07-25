<script setup lang="ts">
import { h, ref, watch } from 'vue'
import { type DataTableColumns, useMessage } from 'naive-ui'
import type { MaterialCodeLibrary } from '@/api/generated'
import { procurementApi } from '@/api/procurement'

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
const keyword = ref('')
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
    ellipsis: { tooltip: true },
    render: (row) => row.name || '—',
  },
  {
    title: '型号',
    key: 'model_spec',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => row.model_spec || '—',
  },
  { title: '计量单位', key: 'unit_name', width: 100 },
  {
    title: '操作',
    key: 'actions',
    width: 88,
    render: (row) =>
      h(
        'button',
        {
          type: 'button',
          class: 'select-action',
          onClick: () => selectItem(row),
        },
        '采用',
      ),
  },
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

function open() {
  keyword.value = ''
  page.value = 1
  show.value = true
  void load()
}

function search() {
  page.value = 1
  void load()
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
    title="选择物料编码"
    style="width: min(980px, 92vw)"
    :mask-closable="false"
  >
    <div class="selector-search">
      <n-input
        v-model:value="keyword"
        clearable
        placeholder="输入名称、型号或物料编码搜索"
        @keyup.enter="search"
      />
      <n-button type="primary" :loading="loading" @click="search">搜索</n-button>
    </div>
    <n-data-table
      remote
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
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  margin-bottom: 16px;
}
.select-action {
  padding: 3px 8px;
  border: 0;
  color: var(--color-primary);
  background: transparent;
  cursor: pointer;
}
.select-action:hover {
  text-decoration: underline;
}
</style>
