<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useDialog, useMessage } from 'naive-ui'
import type { ManagedUser, Role } from '@/api/generated'
import { dictionaryApi } from '@/api/dictionaries'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import { roleLabels } from '@/types/navigation'
import { apiBaseUrl, resolveMcpUrl } from '@/config/env'

const message = useMessage()
const dialog = useDialog()
const items = ref<ManagedUser[]>([])
const loading = ref(false)
const show = ref(false)
const editing = ref<ManagedUser | null>(null)
const mcpUrl = computed(() =>
  editing.value ? resolveMcpUrl(apiBaseUrl, editing.value.api_token) : '',
)
const form = reactive({
  username: '',
  display_name: '',
  role: 'READ_ONLY' as Role,
  enabled: true,
  password: '',
  version: 0,
})
const columns = preventTableColumnCompression<ManagedUser>([
  { title: '用户名', key: 'username', width: tableColumnWidths.identifier },
  { title: '显示名称', key: 'display_name', width: tableColumnWidths.name },
  {
    title: '角色',
    key: 'role',
    width: tableColumnWidths.code,
    render: (r) => roleLabels[r.role],
  },
  {
    title: '状态',
    key: 'enabled',
    width: tableColumnWidths.status,
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
    width: tableColumnWidths.action,
    render: (r) =>
      h('div', { style: 'display:flex;gap:8px' }, [
        h(NButton, { size: 'small', onClick: () => open(r) }, { default: () => '编辑' }),
        h(
          NButton,
          { size: 'small', type: 'error', secondary: true, onClick: () => remove(r) },
          { default: () => '删除' },
        ),
      ]),
  },
])
const tableScrollX = getTableScrollX(columns)
async function load() {
  loading.value = true
  try {
    items.value = (await dictionaryApi.users({ page_size: 200 })).items
  } finally {
    loading.value = false
  }
}
function open(row?: ManagedUser) {
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
    const payload = {
      username: form.username,
      display_name: form.display_name,
      role: form.role,
      enabled: form.enabled,
      ...(form.password ? { password: form.password } : {}),
    }
    if (editing.value) {
      await dictionaryApi.updateUser(editing.value.id, { ...payload, version: form.version })
    } else {
      await dictionaryApi.createUser({ ...payload, password: form.password })
    }
    message.success('保存成功')
    show.value = false
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '保存失败')
  }
}
async function copyApiToken() {
  if (!editing.value) return
  try {
    await navigator.clipboard.writeText(editing.value.api_token)
    message.success('接口令牌已复制')
  } catch {
    message.error('复制失败，请手动选择令牌')
  }
}
async function copyMcpUrl() {
  if (!mcpUrl.value) return
  try {
    await navigator.clipboard.writeText(mcpUrl.value)
    message.success('MCP 地址已复制')
  } catch {
    message.error('复制失败，请手动选择地址')
  }
}
function regenerateApiToken() {
  if (!editing.value) return
  dialog.warning({
    draggable: true,
    title: '重新生成接口令牌',
    content: `重新生成后，“${editing.value.username}”的旧令牌将立即失效。`,
    positiveText: '重新生成',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const updated = await dictionaryApi.regenerateUserApiToken(
          editing.value!.id,
          editing.value!.version,
        )
        editing.value = updated
        form.version = updated.version
        const index = items.value.findIndex((item) => item.id === updated.id)
        if (index >= 0) items.value[index] = updated
        message.success('接口令牌已重新生成')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '重新生成失败')
        return false
      }
    },
  })
}
function remove(row: ManagedUser) {
  dialog.warning({
    draggable: true,
    title: '删除用户',
    content: `确认删除用户“${row.username}”吗？已有操作记录或业务数据关联的用户不能删除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await dictionaryApi.deleteUser(row.id)
        message.success('用户已删除')
        await load()
      } catch (e) {
        message.error(e instanceof Error ? e.message : '删除失败')
        return false
      }
    },
  })
}
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">管理端用户</h1>
      </div>
      <n-button type="primary" @click="open()">新建用户</n-button>
    </div>
    <n-card class="data-card"
      ><n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="tableScrollX"
        :row-key="(r: ManagedUser) => r.id" /></n-card
    ><n-modal
      v-model:show="show"
      preset="card"
      draggable
      :title="editing ? '编辑管理端用户' : '新建管理端用户'"
      style="width: min(620px, calc(100vw - 32px))"
      ><n-form label-placement="top"
        ><n-form-item label="用户名" required><n-input v-model:value="form.username" /></n-form-item
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
        ><n-form-item v-if="editing" label="接口令牌"
          ><n-input-group>
            <n-input :value="editing.api_token" readonly />
            <n-button @click="copyApiToken">复制令牌</n-button>
            <n-button @click="regenerateApiToken">重新生成</n-button>
          </n-input-group></n-form-item
        ><n-form-item v-if="editing" label="MCP 地址"
          ><n-input-group>
            <n-input :value="mcpUrl" readonly />
            <n-button type="primary" secondary @click="copyMcpUrl">复制地址</n-button>
          </n-input-group></n-form-item
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
