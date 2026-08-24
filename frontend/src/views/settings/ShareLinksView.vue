<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { NButton, NCheckbox, NTag, useDialog, useMessage } from 'naive-ui'
import type { ShareListRead, ShareType } from '@/api/generated'
import { shareApi } from '@/api/share'
import { shareColumnOptions, type ShareColumnOption } from '@/constants/shareColumns'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import { usePagedTable } from '@/composables/usePagedTable'
import { formatShanghaiTime } from '@/utils/time'

const message = useMessage()
const dialog = useDialog()
const { items, total, page, pageSize, loading, load, changePage, changePageSize } = usePagedTable<
  ShareListRead,
  Record<string, never>
>({
  fetch: (_filters, pager) => shareApi.listShares({ page: pager.page, page_size: pager.page_size }),
  initialFilters: () => ({}),
  defaultPageSize: 20,
})

const shareTypeLabels: Record<ShareType, string> = {
  purchase_plan: '申购计划',
  purchase_record: '申购记录',
}

// ---- 设置列弹窗 ----
const showColumnsModal = ref(false)
const editingColumns = ref<ShareListRead | null>(null)
const showAllColumns = ref(true)
const selectedColumns = ref<string[]>([])
const savingColumns = ref(false)

const columnOptions = computed<ShareColumnOption[]>(() =>
  editingColumns.value ? shareColumnOptions(editingColumns.value.share_type) : [],
)

function openColumnsModal(row: ShareListRead) {
  editingColumns.value = row
  const allKeys = shareColumnOptions(row.share_type).map((option) => option.key)
  if (row.columns == null) {
    showAllColumns.value = true
    selectedColumns.value = allKeys
  } else {
    showAllColumns.value = false
    selectedColumns.value = allKeys.filter((key) => row.columns?.includes(key))
  }
  showColumnsModal.value = true
}

function toggleColumn(key: string, checked: boolean) {
  if (!checked && selectedColumns.value.length === 1) return
  selectedColumns.value = checked
    ? [...selectedColumns.value, key]
    : selectedColumns.value.filter((current) => current !== key)
}

async function saveColumns() {
  if (!editingColumns.value) return
  if (!showAllColumns.value && selectedColumns.value.length === 0) {
    message.warning('请至少保留 1 列')
    return
  }
  savingColumns.value = true
  try {
    await shareApi.updateShareColumns(
      editingColumns.value.token,
      showAllColumns.value ? null : selectedColumns.value,
    )
    message.success('展示列已更新')
    showColumnsModal.value = false
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    savingColumns.value = false
  }
}

function columnLabels(row: ShareListRead): string {
  if (row.columns == null) return '展示全部列'
  const options = shareColumnOptions(row.share_type)
  return row.columns
    .map((key) => options.find((option) => option.key === key)?.label ?? key)
    .join('、')
}

async function copyLink(token: string) {
  try {
    await navigator.clipboard.writeText(`${window.location.origin}/share/${token}`)
    message.success('分享链接已复制')
  } catch {
    message.warning('复制失败，请手动复制')
  }
}

function revoke(row: ShareListRead) {
  dialog.warning({
    draggable: true,
    title: '撤回分享链接',
    content: `撤回后，该「${shareTypeLabels[row.share_type]}」分享链接将立即失效，任何持有链接的人都无法再查看。`,
    positiveText: '撤回',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await shareApi.revokeShare(row.token)
        message.success('分享链接已撤回')
        await load()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '撤回失败')
        return false
      }
    },
  })
}

const columns = preventTableColumnCompression<ShareListRead>([
  {
    title: '类型',
    key: 'share_type',
    width: tableColumnWidths.status,
    render: (row) =>
      h(
        NTag,
        { size: 'small', bordered: false, round: true, type: 'primary' },
        { default: () => shareTypeLabels[row.share_type] },
      ),
  },
  { title: '条数', key: 'item_count', width: 80, align: 'right' },
  {
    title: '展示列',
    key: 'columns',
    width: 150,
    render: (row) => {
      const columns = row.columns
      if (columns == null)
        return h(
          NTag,
          { size: 'small', bordered: false, round: true, type: 'success' },
          { default: () => '全部列' },
        )
      return h(
        NTag,
        { size: 'small', bordered: false, round: true, type: 'info', title: columnLabels(row) },
        { default: () => `已展示 ${columns.length} 列` },
      )
    },
  },
  {
    title: '失效时间',
    key: 'expires_at',
    width: tableColumnWidths.datetime,
    render: (row) =>
      row.expires_at
        ? formatShanghaiTime(row.expires_at)
        : h(
            NTag,
            { size: 'small', bordered: false, round: true, type: 'success' },
            { default: () => '永久' },
          ),
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: tableColumnWidths.datetime,
    render: (row) => formatShanghaiTime(row.created_at),
  },
  {
    title: '创建人',
    key: 'created_by_name',
    width: tableColumnWidths.person,
    render: (row) => row.created_by_name ?? '—',
  },
  {
    title: '操作',
    key: 'action',
    width: 210,
    render: (row) =>
      h('div', { style: 'display:flex;gap:8px' }, [
        h(
          NButton,
          { size: 'small', secondary: true, onClick: () => void copyLink(row.token) },
          { default: () => '复制链接' },
        ),
        h(
          NButton,
          { size: 'small', onClick: () => openColumnsModal(row) },
          { default: () => '设置列' },
        ),
        h(
          NButton,
          { size: 'small', type: 'error', secondary: true, onClick: () => revoke(row) },
          { default: () => '撤回' },
        ),
      ]),
  },
])
const tableScrollX = getTableScrollX(columns)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">分享链接</h1>
      </div>
    </div>
    <n-card class="data-card"
      ><n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :scroll-x="tableScrollX"
        :row-key="(r: ShareListRead) => r.token"
      />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :item-count="total"
          :page-sizes="[10, 20, 50, 100, 200]"
          show-size-picker
          @update:page="changePage"
          @update:page-size="changePageSize"
        />
      </div>
    </n-card>

    <n-modal
      v-model:show="showColumnsModal"
      preset="card"
      draggable
      title="设置分享页展示列"
      style="width: min(620px, calc(100vw - 32px))"
      :mask-closable="false"
    >
      <template v-if="editingColumns">
        <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
          该「{{ shareTypeLabels[editingColumns.share_type] }}」分享链接当前
          <b>{{
            editingColumns.columns == null
              ? '展示全部列'
              : `展示 ${editingColumns.columns.length} 列`
          }}</b
          >。取消勾选的列在公开页不再展示，且其数据不会随分享响应下发。
        </n-alert>
        <n-form label-placement="top">
          <n-form-item label="展示范围">
            <n-space align="center">
              <n-switch v-model:value="showAllColumns" />
              <span>{{ showAllColumns ? '展示全部列' : '仅展示勾选的列' }}</span>
            </n-space>
          </n-form-item>
          <n-form-item v-if="!showAllColumns" label="选择展示字段（至少保留 1 个）">
            <n-checkbox-group v-model:value="selectedColumns" class="column-check-grid">
              <n-checkbox
                v-for="option in columnOptions"
                :key="option.key"
                :value="option.key"
                :disabled="selectedColumns.length === 1 && selectedColumns[0] === option.key"
                @update:checked="toggleColumn(option.key, $event)"
              >
                {{ option.label }}
              </n-checkbox>
            </n-checkbox-group>
          </n-form-item>
        </n-form>
      </template>
      <template #footer>
        <n-space justify="end">
          <n-button :disabled="savingColumns" @click="showColumnsModal = false">取消</n-button>
          <n-button type="primary" :loading="savingColumns" @click="saveColumns">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
}

.column-check-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px 20px;
}

@media (max-width: 640px) {
  .column-check-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
