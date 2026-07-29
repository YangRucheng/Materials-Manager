<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NEllipsis, NTag, useDialog, useMessage } from 'naive-ui'
import type { MiniProgramUser } from '@/api/generated'
import { dictionaryApi } from '@/api/dictionaries'
import { formatShanghaiTime } from '@/utils/time'
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
const merging = ref(false)
const show = ref(false)
const showMerge = ref(false)
const editing = ref<MiniProgramUser | null>(null)
const mergeTargetId = ref<number | null>(null)
const form = reactive({
  display_name: '',
  department_name: '',
  enabled: true,
  version: 0,
})
const columns = preventTableColumnCompression<MiniProgramUser>([
  { title: '姓名', key: 'display_name', width: 136 },
  { title: '部门单位', key: 'department_name', width: 240, ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'enabled',
    width: 88,
    render: (row) =>
      h(
        NTag,
        { type: row.enabled ? 'success' : 'warning' },
        { default: () => (row.enabled ? '启用' : '待审核') },
      ),
  },
  {
    title: '注册时间',
    key: 'created_at',
    width: tableColumnWidths.datetime,
    render: (row) => formatShanghaiTime(row.created_at),
  },
  {
    title: '小程序 AppID',
    key: 'app_id',
    width: 190,
    render: (row) =>
      h(
        'div',
        { class: 'identity-list' },
        row.identities.map((identity) =>
          h(NTag, { size: 'small', round: true }, { default: () => identity.app_id }),
        ),
      ),
  },
  {
    title: '微信 OpenID',
    key: 'wechat_openid',
    width: 240,
    render: (row) =>
      h(
        'div',
        { class: 'identity-list' },
        row.identities.map((identity) =>
          h(
            NEllipsis,
            { tooltip: true, class: 'openid-text' },
            { default: () => identity.wechat_openid },
          ),
        ),
      ),
  },
  {
    title: '操作',
    key: 'action',
    width: 84,
    render: (row) =>
      h(
        NButton,
        { size: 'small', secondary: true, onClick: () => open(row) },
        {
          default: () => '编辑',
        },
      ),
  },
])
const tableScrollX = getTableScrollX(columns)
const mergeOptions = computed(() =>
  items.value
    .filter(
      (item) =>
        item.id !== editing.value?.id &&
        item.display_name === editing.value?.display_name &&
        item.department_name === editing.value?.department_name,
    )
    .map((item) => ({
      label: `${item.display_name}（${item.identities.map((identity) => identity.app_id).join('、')}）`,
      value: item.id,
    })),
)

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

function openMerge() {
  mergeTargetId.value = null
  showMerge.value = true
}

async function mergeAccount() {
  const source = editing.value
  const target = items.value.find((item) => item.id === mergeTargetId.value)
  if (!source || !target) {
    message.error('请选择要保留的目标账号')
    return
  }
  merging.value = true
  try {
    await dictionaryApi.mergeMiniProgramUsers(target.id, {
      source_user_id: source.id,
      source_version: source.version,
      target_version: target.version,
    })
    message.success(`已将“${source.display_name}”合并到“${target.display_name}”`)
    showMerge.value = false
    show.value = false
    editing.value = null
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '账号合并失败')
  } finally {
    merging.value = false
  }
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

function confirmDelete() {
  const row = editing.value
  if (!row) return
  dialog.warning({
    draggable: true,
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
      <div>
        <div class="title-row">
          <h1 class="page-title">小程序用户</h1>
          <n-tag round size="small" type="info">{{ items.length }} 位</n-tag>
        </div>
        <p class="page-description">按人员管理多个小程序身份，并支持人工合并重复账号</p>
      </div>
    </div>
    <n-card class="data-card" :bordered="false">
      <n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        size="small"
        :scroll-x="tableScrollX"
        :row-key="(row: MiniProgramUser) => row.id"
      />
    </n-card>
    <n-modal
      v-model:show="show"
      preset="card"
      draggable
      title="编辑小程序用户"
      style="width: 520px"
    >
      <n-form label-placement="top">
        <n-form-item label="已绑定小程序身份">
          <div class="identity-cards">
            <div v-for="identity in editing?.identities" :key="identity.id" class="identity-card">
              <n-tag size="small" round>{{ identity.app_id }}</n-tag>
              <n-ellipsis class="openid-text" :tooltip="true">
                {{ identity.wechat_openid }}
              </n-ellipsis>
            </div>
          </div>
        </n-form-item>
        <n-form-item label="姓名" required>
          <n-input v-model:value="form.display_name" />
        </n-form-item>
        <n-form-item label="部门单位" required>
          <n-input v-model:value="form.department_name" />
        </n-form-item>
        <n-form-item label="用户状态">
          <div class="status-control">
            <n-switch v-model:value="form.enabled" />
            <span>{{ form.enabled ? '已启用' : '待审核' }}</span>
          </div>
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-footer">
          <n-space>
            <n-button
              type="error"
              secondary
              :loading="deletingId === editing?.id"
              @click="confirmDelete"
              >删除用户</n-button
            >
            <n-button secondary :disabled="items.length < 2" @click="openMerge">
              合并账号
            </n-button>
          </n-space>
          <n-space>
            <n-button @click="show = false">取消</n-button>
            <n-button type="primary" @click="save">保存</n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="showMerge"
      preset="card"
      draggable
      title="合并小程序账号"
      style="width: 520px"
    >
      <n-alert type="warning" :bordered="false">
        当前账号“{{
          editing?.display_name
        }}”将被删除，其小程序身份会迁移到目标账号。仅姓名和部门单位完全一致的账号可以合并，历史出库记录不受影响。
      </n-alert>
      <n-form label-placement="top" class="merge-form">
        <n-form-item label="保留的目标账号" required>
          <n-select
            v-model:value="mergeTargetId"
            :options="mergeOptions"
            filterable
            placeholder="请选择确认属于同一人员的账号"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="merge-footer">
          <n-button @click="showMerge = false">取消</n-button>
          <n-button type="warning" :loading="merging" @click="mergeAccount">确认合并</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-description {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 14px;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.status-control {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--color-text-muted);
}

.identity-list,
.identity-cards {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.identity-card {
  display: grid;
  grid-template-columns: minmax(140px, auto) minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  width: 100%;
}

.merge-form {
  margin-top: 18px;
}

.merge-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

:deep(.openid-text) {
  color: var(--color-text-muted);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
}
</style>
