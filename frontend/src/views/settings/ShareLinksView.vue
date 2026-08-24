<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { NButton, NTag, useDialog, useMessage } from 'naive-ui'
import type { ShareListRead, ShareType } from '@/api/generated'
import { shareApi } from '@/api/share'
import {
  defaultShareColumnKeys,
  shareColumnOptions,
  type ShareColumnOption,
} from '@/constants/shareColumns'
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
const selectedColumns = ref<string[]>([])
const savingColumns = ref(false)

const columnOptions = computed<ShareColumnOption[]>(() =>
  editingColumns.value ? shareColumnOptions(editingColumns.value.share_type) : [],
)

function openColumnsModal(row: ShareListRead) {
  editingColumns.value = row
  const allKeys = shareColumnOptions(row.share_type).map((option) => option.key)
  // 未配置列时默认展示列（全部列去掉「状态」）；已配置则按配置回显。
  selectedColumns.value =
    row.columns == null
      ? allKeys.filter((key) => defaultShareColumnKeys(row.share_type).includes(key))
      : allKeys.filter((key) => row.columns?.includes(key))
  showColumnsModal.value = true
}

function toggleColumn(key: string) {
  const selected = selectedColumns.value
  if (selected.includes(key)) {
    if (selected.length === 1) return
    selectedColumns.value = selected.filter((current) => current !== key)
  } else {
    selectedColumns.value = [...selected, key]
  }
}

async function saveColumns() {
  if (!editingColumns.value) return
  if (selectedColumns.value.length === 0) {
    message.warning('请至少保留 1 列')
    return
  }
  savingColumns.value = true
  try {
    await shareApi.updateShareColumns(editingColumns.value.token, selectedColumns.value)
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
  const options = shareColumnOptions(row.share_type)
  const keys = row.columns ?? defaultShareColumnKeys(row.share_type)
  return keys.map((key) => options.find((option) => option.key === key)?.label ?? key).join('、')
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
          {
            size: 'small',
            bordered: false,
            round: true,
            type: 'success',
            title: columnLabels(row),
          },
          { default: () => '默认' },
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
              ? '使用默认展示列（不含「状态」）'
              : `展示 ${editingColumns.columns.length} 列`
          }}</b
          >。取消勾选的列在公开页不再展示，且其数据不会随分享响应下发。
        </n-alert>
        <div class="column-card-grid">
          <button
            v-for="option in columnOptions"
            :key="option.key"
            type="button"
            class="column-card"
            :class="{ selected: selectedColumns.includes(option.key) }"
            :disabled="selectedColumns.length === 1 && selectedColumns[0] === option.key"
            :aria-pressed="selectedColumns.includes(option.key)"
            @click="toggleColumn(option.key)"
          >
            <span class="column-card-check">
              <span v-if="selectedColumns.includes(option.key)" class="column-card-check-icon" />
            </span>
            <span class="column-card-label">{{ option.label }}</span>
          </button>
        </div>
        <p class="column-card-hint">至少保留 1 列</p>
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

.column-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.column-card {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 46px;
  padding: 10px 12px;
  border: 1px solid var(--color-border-subtle);
  border-radius: 10px;
  background: var(--color-surface-soft);
  color: var(--color-text);
  font-size: 14px;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease,
    box-shadow 0.15s ease;
}

.column-card:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.column-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.column-card.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  box-shadow: 0 0 0 1px var(--color-primary) inset;
  color: var(--color-primary);
  font-weight: 600;
}

.column-card:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.column-card-check {
  display: grid;
  width: 20px;
  height: 20px;
  flex: none;
  place-items: center;
  border: 1.5px solid var(--color-border);
  border-radius: 6px;
  background: #fff;
}

.column-card.selected .column-card-check {
  border-color: var(--color-primary);
  background: var(--color-primary);
}

.column-card-check-icon {
  width: 10px;
  height: 6px;
  border-left: 2px solid #fff;
  border-bottom: 2px solid #fff;
  transform: rotate(-45deg) translateY(-1px);
}

.column-card-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.column-card-hint {
  margin: 12px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

@media (max-width: 640px) {
  .column-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
