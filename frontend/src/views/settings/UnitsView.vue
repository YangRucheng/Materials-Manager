<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useMessage, type DataTableColumns } from 'naive-ui'
import type { MeasurementUnit } from '@/api/generated'
import { dictionaryApi } from '@/api/dictionaries'
import { useDictionaryStore } from '@/stores/dictionaries'

const message = useMessage()
const store = useDictionaryStore()
const items = ref<MeasurementUnit[]>([])
const loading = ref(false)
const show = ref(false)
const editing = ref<MeasurementUnit | null>(null)
const form = reactive({
  code: '',
  name: '',
  decimal_places: 0 as 0 | 1,
  enabled: true,
  version: 0,
})
const columns: DataTableColumns<MeasurementUnit> = [
  { title: '编码', key: 'code' },
  { title: '名称', key: 'name' },
  { title: '数量小数位', key: 'decimal_places' },
  {
    title: '状态',
    key: 'enabled',
    render: (r) =>
      h(
        NTag,
        { type: r.enabled ? 'success' : 'default' },
        { default: () => (r.enabled ? '启用' : '停用') },
      ),
  },
  {
    title: '操作',
    key: 'action',
    render: (r) => h(NButton, { size: 'small', onClick: () => open(r) }, { default: () => '编辑' }),
  },
]
async function load() {
  loading.value = true
  try {
    items.value = (await dictionaryApi.units({ page_size: 200 })).items
  } finally {
    loading.value = false
  }
}
function open(row?: MeasurementUnit) {
  editing.value = row || null
  Object.assign(
    form,
    row
      ? {
          code: row.code,
          name: row.name,
          decimal_places: row.decimal_places,
          enabled: row.enabled,
          version: row.version,
        }
      : { code: '', name: '', decimal_places: 0, enabled: true, version: 0 },
  )
  show.value = true
}
async function save() {
  if (!form.code.trim() || !form.name.trim()) {
    message.error('编码和名称必填')
    return
  }
  try {
    if (editing.value) await dictionaryApi.updateUnit(editing.value.id, form)
    else await dictionaryApi.createUnit(form)
    message.success('保存成功')
    show.value = false
    await load()
    await store.load(true)
  } catch (e) {
    message.error(e instanceof Error ? e.message : '保存失败')
  }
}
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">计量单位</h1>
        <p class="page-subtitle">数量输入按单位限制为整数或 1 位小数</p>
      </div>
      <n-button type="primary" @click="open()">新建单位</n-button>
    </div>
    <n-card
      ><n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(r: MeasurementUnit) => r.id" /></n-card
    ><n-modal
      v-model:show="show"
      preset="card"
      :title="editing ? '编辑单位' : '新建单位'"
      style="width: 500px"
      ><n-form label-placement="top"
        ><n-form-item label="编码" required
          ><n-input v-model:value="form.code" maxlength="32" /></n-form-item
        ><n-form-item label="名称" required
          ><n-input v-model:value="form.name" maxlength="32" /></n-form-item
        ><n-form-item label="小数位"
          ><n-select
            v-model:value="form.decimal_places"
            :options="[0, 1].map((x) => ({ label: String(x), value: x }))" /></n-form-item
        ><n-form-item label="启用"><n-switch v-model:value="form.enabled" /></n-form-item></n-form
      ><template #footer
        ><n-space justify="end"
          ><n-button @click="show = false">取消</n-button
          ><n-button type="primary" @click="save">保存</n-button></n-space
        ></template
      ></n-modal
    >
  </div>
</template>
