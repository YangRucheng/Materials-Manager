<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, useMessage, type FormInst, type FormRules } from 'naive-ui'
import { inventoryApi } from '@/api/inventory'
import type { FileObject, StockMaterial, StockMaterialWrite } from '@/api/generated'
import { useDictionaryStore } from '@/stores/dictionaries'
import { useAuthStore } from '@/stores/auth'
import ImageUploader from '@/components/ImageUploader.vue'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'

const message = useMessage()
const auth = useAuthStore()
const dictionaries = useDictionaryStore()
const loading = ref(false)
const items = ref<StockMaterial[]>([])
const total = ref(0)
const page = ref(1)
const filters = reactive({ keyword: '' })
const showModal = ref(false)
const saving = ref(false)
const editing = ref<StockMaterial | null>(null)
const formRef = ref<FormInst | null>(null)
const images = ref<FileObject[]>([])
const form = reactive<StockMaterialWrite>({
  name: '',
  model_spec: '',
  unit_id: null,
  remark: '',
  image_ids: [],
})
const rules: FormRules = {
  name: { required: true, message: '请输入物资名称' },
  model_spec: { required: true, message: '请输入型号规格；无型号时填写“无”' },
  unit_id: { type: 'number', required: true, message: '请选择单位' },
}

const columns = preventTableColumnCompression<StockMaterial>([
  {
    title: '物资名称',
    key: 'name',
    width: tableColumnWidths.name,
    render: (row) => row.name,
  },
  {
    title: '型号规格',
    key: 'model_spec',
    width: tableColumnWidths.model,
    ellipsis: { tooltip: true },
  },
  { title: '单位', key: 'unit_name', width: tableColumnWidths.unit },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) =>
      auth.can('warehouse:write')
        ? h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' })
        : '—',
  },
])
const tableScrollX = getTableScrollX(columns)
async function load() {
  loading.value = true
  try {
    const data = await inventoryApi.materials({
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
function resetForm() {
  Object.assign(form, { name: '', model_spec: '', unit_id: null, remark: '', image_ids: [] })
  images.value = []
  editing.value = null
}
function openCreate() {
  resetForm()
  showModal.value = true
}
function openEdit(row: StockMaterial) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    model_spec: row.model_spec,
    unit_id: row.unit_id,
    remark: row.remark || '',
    image_ids: row.images.map((x) => x.id),
    version: row.version,
  })
  images.value = [...row.images]
  showModal.value = true
}
async function save() {
  await formRef.value?.validate()
  saving.value = true
  try {
    form.image_ids = images.value.map((x) => x.id)
    if (editing.value) await inventoryApi.updateMaterial(editing.value.id, form)
    else await inventoryApi.createMaterial(form)
    message.success('保存成功')
    showModal.value = false
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}
onMounted(() => {
  void dictionaries.load()
  void load()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">物资档案</h1>
      </div>
      <n-button v-if="auth.can('warehouse:write')" type="primary" @click="openCreate"
        >新建物资</n-button
      >
    </div>
    <n-card class="filter-card"
      ><div class="filter-bar">
        <n-input
          v-model:value="filters.keyword"
          clearable
          placeholder="名称或型号规格"
          style="width: 240px"
          @keyup.enter="query"
        /><n-button type="primary" @click="query">查询</n-button>
      </div></n-card
    >
    <n-card class="data-card"
      ><n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="tableScrollX"
        :row-key="(row: StockMaterial) => row.id" />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          :item-count="total"
          :page-size="20"
          @update:page="load"
        /></div
    ></n-card>
    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="editing ? '编辑二级库物资' : '新建二级库物资'"
      style="width: 680px"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top"
        ><div class="form-grid">
          <n-form-item label="物资名称" path="name"
            ><n-input v-model:value="form.name" maxlength="128" /></n-form-item
          ><n-form-item label="型号规格" path="model_spec"
            ><n-input
              v-model:value="form.model_spec"
              maxlength="255"
              placeholder="无型号时填写“无”" /></n-form-item
          ><n-form-item label="计量单位" path="unit_id"
            ><n-select v-model:value="form.unit_id" :options="dictionaries.unitOptions"
          /></n-form-item>
        </div>
        <n-form-item label="备注"
          ><n-input
            v-model:value="form.remark"
            type="textarea"
            maxlength="1000"
            show-count /></n-form-item
        ><n-form-item label="图片附件"><ImageUploader v-model:files="images" /></n-form-item
      ></n-form>
      <template #footer
        ><n-space justify="end"
          ><n-button @click="showModal = false">取消</n-button
          ><n-button type="primary" :loading="saving" @click="save">保存</n-button></n-space
        ></template
      >
    </n-modal>
  </div>
</template>
