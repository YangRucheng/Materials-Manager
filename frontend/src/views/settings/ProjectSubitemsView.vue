<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useMessage, type DataTableColumns } from 'naive-ui'
import type { ProjectSubitem } from '@/api/generated'
import { dictionaryApi } from '@/api/dictionaries'
import { useDictionaryStore } from '@/stores/dictionaries'

const message = useMessage()
const store = useDictionaryStore()
const items = ref<ProjectSubitem[]>([])
const loading = ref(false)
const show = ref(false)
const editing = ref<ProjectSubitem | null>(null)
const keyword = ref('')
const form = reactive({
  project_code: '',
  project_name: '',
  subitem_no: '',
  subitem_name: '',
  enabled: true,
  version: 0,
})
const columns: DataTableColumns<ProjectSubitem> = [
  { title: '项目编码', key: 'project_code' },
  { title: '项目名称', key: 'project_name' },
  { title: '子项号', key: 'subitem_no' },
  { title: '子项名称', key: 'subitem_name' },
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
    items.value = (
      await dictionaryApi.projects({ page_size: 200, keyword: keyword.value || undefined })
    ).items
  } finally {
    loading.value = false
  }
}
function open(row?: ProjectSubitem) {
  editing.value = row || null
  Object.assign(
    form,
    row
      ? {
          project_code: row.project_code,
          project_name: row.project_name,
          subitem_no: row.subitem_no,
          subitem_name: row.subitem_name,
          enabled: row.enabled,
          version: row.version,
        }
      : {
          project_code: '',
          project_name: '',
          subitem_no: '',
          subitem_name: '',
          enabled: true,
          version: 0,
        },
  )
  show.value = true
}
async function save() {
  if (
    !form.project_code.trim() ||
    !form.project_name.trim() ||
    !form.subitem_no.trim() ||
    !form.subitem_name.trim()
  ) {
    message.error('请完整填写项目与子项信息')
    return
  }
  try {
    if (editing.value) await dictionaryApi.updateProject(editing.value.id, form)
    else await dictionaryApi.createProject(form)
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
        <h1 class="page-title">项目子项</h1>
        <p class="page-subtitle">请购与出库使用的项目、子项基础数据</p>
      </div>
      <n-button type="primary" @click="open()">新建项目子项</n-button>
    </div>
    <n-card
      ><div class="filter-bar">
        <n-input
          v-model:value="keyword"
          clearable
          placeholder="项目、子项号或名称"
          style="width: 260px"
        /><n-button type="primary" @click="load">查询</n-button>
      </div></n-card
    ><n-card
      ><n-data-table
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(r: ProjectSubitem) => r.id" /></n-card
    ><n-modal
      v-model:show="show"
      preset="card"
      :title="editing ? '编辑项目子项' : '新建项目子项'"
      style="width: 620px"
      ><n-form label-placement="top"
        ><div class="form-grid">
          <n-form-item label="项目编码" required
            ><n-input v-model:value="form.project_code" /></n-form-item
          ><n-form-item label="项目名称" required
            ><n-input v-model:value="form.project_name" /></n-form-item
          ><n-form-item label="子项号" required
            ><n-input v-model:value="form.subitem_no" /></n-form-item
          ><n-form-item label="子项名称" required
            ><n-input v-model:value="form.subitem_name"
          /></n-form-item>
        </div>
        <n-form-item label="启用"><n-switch v-model:value="form.enabled" /></n-form-item></n-form
      ><template #footer
        ><n-space justify="end"
          ><n-button @click="show = false">取消</n-button
          ><n-button type="primary" @click="save">保存</n-button></n-space
        ></template
      ></n-modal
    >
  </div>
</template>
