<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useMessage, type DataTableColumns } from 'naive-ui'
import type { Role, User } from '@/api/generated'
import { dictionaryApi } from '@/api/dictionaries'
import { roleLabels } from '@/types/navigation'

const message = useMessage()
const items = ref<User[]>([])
const loading = ref(false)
const show = ref(false)
const editing = ref<User | null>(null)
const form = reactive({
  username: '',
  display_name: '',
  role: 'READ_ONLY' as Role,
  enabled: true,
  password: '',
  version: 0,
})
const columns: DataTableColumns<User> = [
  { title: '用户名', key: 'username' },
  { title: '显示名称', key: 'display_name' },
  { title: '角色', key: 'role', render: (r) => roleLabels[r.role] },
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
    items.value = (await dictionaryApi.users({ page_size: 200 })).items
  } finally {
    loading.value = false
  }
}
function open(row?: User) {
  editing.value = row || null
  Object.assign(
    form,
    row
      ? {
          username: row.username,
          display_name: row.display_name,
          role: row.role,
          enabled: row.enabled,
          password: '',
          version: row.version,
        }
      : {
          username: '',
          display_name: '',
          role: 'READ_ONLY',
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
    if (editing.value) await dictionaryApi.updateUser(editing.value.id, form)
    else await dictionaryApi.createUser(form)
    message.success('保存成功')
    show.value = false
    await load()
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
        <h1 class="page-title">用户管理</h1>
        <p class="page-subtitle">每个用户直接配置一个简单角色</p>
      </div>
      <n-button type="primary" @click="open()">新建用户</n-button>
    </div>
    <n-card
      ><n-data-table
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(r: User) => r.id" /></n-card
    ><n-modal
      v-model:show="show"
      preset="card"
      :title="editing ? '编辑用户' : '新建用户'"
      style="width: 520px"
      ><n-form label-placement="top"
        ><n-form-item label="用户名" required
          ><n-input v-model:value="form.username" :disabled="Boolean(editing)" /></n-form-item
        ><n-form-item label="显示名称" required
          ><n-input v-model:value="form.display_name" /></n-form-item
        ><n-form-item label="角色"
          ><n-select
            v-model:value="form.role"
            :options="
              Object.entries(roleLabels).map(([value, label]) => ({ value, label }))
            " /></n-form-item
        ><n-form-item
          :label="editing ? '重置密码（不修改可留空）' : '初始密码'"
          :required="!editing"
          ><n-input
            v-model:value="form.password"
            type="password"
            show-password-on="click" /></n-form-item
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
