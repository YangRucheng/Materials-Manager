<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import type { MiniProgramUser } from '@/api/generated'
import { dictionaryApi } from '@/api/dictionaries'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'

const message = useMessage()
const items = ref<MiniProgramUser[]>([])
const loading = ref(false)
const show = ref(false)
const editing = ref<MiniProgramUser | null>(null)
const form = reactive({
  username: '',
  display_name: '',
  enabled: true,
  password: '',
  version: 0,
})
const columns = preventTableColumnCompression<MiniProgramUser>([
  { title: '用户名', key: 'username', width: tableColumnWidths.identifier },
  { title: '显示名称', key: 'display_name', width: tableColumnWidths.name },
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
    width: tableColumnWidths.action,
    render: (row) =>
      h(NButton, { size: 'small', onClick: () => open(row) }, { default: () => '编辑' }),
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

function open(row?: MiniProgramUser) {
  editing.value = row || null
  Object.assign(
    form,
    row
      ? {
          username: row.username,
          display_name: row.display_name,
          enabled: row.enabled,
          password: '',
          version: row.version,
        }
      : {
          username: '',
          display_name: '',
          enabled: true,
          password: '',
          version: 0,
        },
  )
  show.value = true
}

async function save() {
  if (!form.username.trim() || !form.display_name.trim() || (!editing.value && !form.password)) {
    message.error('请完整填写用户名、显示名称和初始密码')
    return
  }
  try {
    const payload = {
      username: form.username,
      display_name: form.display_name,
      enabled: form.enabled,
      ...(form.password ? { password: form.password } : {}),
    }
    if (editing.value) {
      await dictionaryApi.updateMiniProgramUser(editing.value.id, {
        ...payload,
        version: form.version,
      })
    } else {
      await dictionaryApi.createMiniProgramUser({ ...payload, password: form.password })
    }
    message.success('保存成功')
    show.value = false
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1 class="page-title">小程序用户</h1>
      <n-button type="primary" @click="open()">新建用户</n-button>
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
    <n-modal
      v-model:show="show"
      preset="card"
      :title="editing ? '编辑小程序用户' : '新建小程序用户'"
      style="width: 520px"
    >
      <n-form label-placement="top">
        <n-form-item label="用户名" required><n-input v-model:value="form.username" /></n-form-item>
        <n-form-item label="显示名称" required>
          <n-input v-model:value="form.display_name" />
        </n-form-item>
        <n-form-item
          :label="editing ? '重置密码（不修改可留空）' : '初始密码'"
          :required="!editing"
        >
          <n-input v-model:value="form.password" type="password" show-password-on="click" />
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
