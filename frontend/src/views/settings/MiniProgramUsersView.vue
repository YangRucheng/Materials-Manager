<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useDialog, useMessage } from 'naive-ui'
import type { MiniProgramUser } from '@/api/generated'
import { dictionaryApi } from '@/api/dictionaries'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'

const message = useMessage()
const dialog = useDialog()
const items = ref<MiniProgramUser[]>([])
const loading = ref(false)
const deletingId = ref<number | null>(null)
const show = ref(false)
const editing = ref<MiniProgramUser | null>(null)
const form = reactive({
  display_name: '',
  department_name: '',
  enabled: true,
  version: 0,
})
const columns = preventTableColumnCompression<MiniProgramUser>([
  { title: '微信 OpenID', key: 'wechat_openid', width: tableColumnWidths.identifier * 2 },
  { title: '姓名', key: 'display_name', width: tableColumnWidths.name },
  { title: '部门单位', key: 'department_name', width: tableColumnWidths.name * 2 },
  {
    title: '状态',
    key: 'enabled',
    width: tableColumnWidths.status,
    render: (row) =>
      h(
        NTag,
        { type: row.enabled ? 'success' : 'default' },
        { default: () => (row.enabled ? '启用' : '停用') },
      ),
  },
  {
    title: '操作',
    key: 'action',
    width: tableColumnWidths.action * 2,
    render: (row) =>
      h('div', { class: 'table-actions' }, [
        h(NButton, { size: 'small', onClick: () => open(row) }, { default: () => '编辑' }),
        h(
          NButton,
          {
            size: 'small',
            type: 'error',
            secondary: true,
            loading: deletingId.value === row.id,
            onClick: () => confirmDelete(row),
          },
          { default: () => '删除' },
        ),
      ]),
  },
])
const tableScrollX = getTableScrollX(columns)

async function load() {
  loading.value = true
  try {
    items.value = (await dictionaryApi.miniProgramUsers({ page_size: 200 })).items
  } finally {
    loading.value = false
  }
}

function open(row: MiniProgramUser) {
  editing.value = row
  Object.assign(form, {
    display_name: row.display_name,
    department_name: row.department_name,
    enabled: row.enabled,
    version: row.version,
  })
  show.value = true
}

async function save() {
  if (!editing.value || !form.display_name.trim() || !form.department_name.trim()) {
    message.error('请填写姓名和部门单位')
    return
  }
  try {
    await dictionaryApi.updateMiniProgramUser(editing.value.id, {
      display_name: form.display_name,
      department_name: form.department_name,
      enabled: form.enabled,
      version: form.version,
    })
    message.success('保存成功')
    show.value = false
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  }
}

function confirmDelete(row: MiniProgramUser) {
  dialog.warning({
    title: '删除小程序用户',
    content: `确认删除“${row.display_name}”？删除后，该微信用户可重新填写姓名和部门单位完成绑定。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      deletingId.value = row.id
      try {
        await dictionaryApi.deleteMiniProgramUser(row.id, row.version)
        message.success('已删除，该用户可以重新绑定资料')
        if (editing.value?.id === row.id) show.value = false
        await load()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '删除失败')
      } finally {
        deletingId.value = null
      }
    },
  })
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">小程序用户</h1>
    </div>
    <n-card class="data-card" :bordered="false">
      <n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="tableScrollX"
        :row-key="(row: MiniProgramUser) => row.id"
      />
    </n-card>
    <n-modal v-model:show="show" preset="card" title="编辑小程序用户" style="width: 520px">
      <n-form label-placement="top">
        <n-form-item label="微信 OpenID">
          <n-input :value="editing?.wechat_openid" disabled />
        </n-form-item>
        <n-form-item label="姓名" required>
          <n-input v-model:value="form.display_name" />
        </n-form-item>
        <n-form-item label="部门单位" required>
          <n-input v-model:value="form.department_name" />
        </n-form-item>
        <n-form-item label="启用"><n-switch v-model:value="form.enabled" /></n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="show = false">取消</n-button>
          <n-button type="primary" @click="save">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
:deep(.table-actions) {
  display: flex;
  gap: 8px;
}
</style>
