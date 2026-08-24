<script setup lang="ts">
import { computed, h, onMounted, ref, type VNodeChild } from 'vue'
import { useRoute } from 'vue-router'
import { NTag, type DataTableColumns } from 'naive-ui'
import type { FileObject, SharePublicView } from '@/api/generated'
import { shareApi } from '@/api/share'
import { AppError } from '@/api/client'
import ImageThumbnails from '@/components/ImageThumbnails.vue'
import { formatDate, formatShanghaiTime } from '@/utils/time'

const route = useRoute()

const loading = ref(true)
const error = ref('')
const data = ref<SharePublicView | null>(null)

const isRecord = computed(() => data.value?.share_type === 'purchase_record')
const title = computed(() => (isRecord.value ? '申购记录' : '申购计划'))
const createdLabel = computed(() => (data.value ? formatShanghaiTime(data.value.created_at) : '—'))
const expiryLabel = computed(() => {
  if (!data.value) return '—'
  return data.value.expires_at ? formatShanghaiTime(data.value.expires_at) : '永久有效'
})

/** 匿名分享行：列配置时为仅含所选列（+行身份键）的字典。 */
type ShareRow = Record<string, unknown>

function renderStatus(value: unknown) {
  const status = value == null ? '' : String(value)
  const typeMap: Record<string, 'success' | 'warning' | 'info' | 'default'> = {
    正常: 'success',
    已申购: 'info',
    暂不申购: 'warning',
    已归档: 'default',
  }
  return h(
    NTag,
    { size: 'small', bordered: false, round: true, type: typeMap[status] ?? 'default' },
    { default: () => status },
  )
}

const renderName = (value: unknown) => h('span', { class: 'cell-name' }, String(value ?? ''))

const renderQuantity = (value: unknown, unit: unknown) => {
  if (value == null || value === '') return '—'
  return `${value}${unit ?? ''}`
}

interface ShareColumnDef {
  key: string
  title: string
  width: number
  align?: 'left' | 'right'
  ellipsis?: { tooltip: true }
  render?: (row: ShareRow) => VNodeChild
}

const planColumnDefs: ShareColumnDef[] = [
  {
    key: 'plan_date',
    title: '需求日期',
    width: 110,
    render: (row) => formatDate(String(row.plan_date)),
  },
  {
    key: 'material_code',
    title: '物料编码',
    width: 130,
    render: (row) => String(row.material_code ?? '—'),
  },
  { key: 'category', title: '类别', width: 100, render: (row) => String(row.category ?? '—') },
  { key: 'urgency', title: '紧急程度', width: 90, render: (row) => String(row.urgency ?? '') },
  {
    key: 'demand_department',
    title: '需求部门',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => String(row.demand_department ?? ''),
  },
  { key: 'name', title: '名称', width: 170, render: (row) => renderName(row.name) },
  {
    key: 'model_spec',
    title: '型号规格',
    width: 190,
    ellipsis: { tooltip: true },
    render: (row) => String(row.model_spec ?? ''),
  },
  {
    key: 'planned_qty',
    title: '计划数量',
    width: 110,
    align: 'right',
    render: (row) => renderQuantity(row.planned_qty, row.unit_name),
  },
  {
    key: 'actual_demand_person',
    title: '实际需求人',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => String(row.actual_demand_person ?? ''),
  },
  {
    key: 'purchase_responsible',
    title: '申购负责人',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => String(row.purchase_responsible ?? ''),
  },
  { key: 'subitem_no', title: '子项号', width: 90, render: (row) => String(row.subitem_no ?? '—') },
  {
    key: 'usage',
    title: '用途',
    width: 210,
    ellipsis: { tooltip: true },
    render: (row) => String(row.usage ?? ''),
  },
  { key: 'status', title: '状态', width: 100, render: (row) => renderStatus(row.status) },
  {
    key: 'images',
    title: '图片',
    width: 150,
    render: (row) => h(ImageThumbnails, { images: (row.images ?? []) as FileObject[] }),
  },
]

const recordColumnDefs: ShareColumnDef[] = [
  {
    key: 'plan_date',
    title: '需求日期',
    width: 110,
    render: (row) => formatDate(String(row.plan_date)),
  },
  {
    key: 'purchase_order_no',
    title: '申购单号',
    width: 140,
    render: (row) => String(row.purchase_order_no ?? '—'),
  },
  { key: 'trace_no', title: '追溯号', width: 130, render: (row) => String(row.trace_no ?? '—') },
  { key: 'category', title: '类别', width: 100, render: (row) => String(row.category ?? '—') },
  {
    key: 'demand_department',
    title: '需求部门',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => String(row.demand_department ?? ''),
  },
  {
    key: 'material_name',
    title: '物资名称',
    width: 180,
    render: (row) => renderName(row.material_name),
  },
  {
    key: 'model_spec',
    title: '型号规格',
    width: 190,
    ellipsis: { tooltip: true },
    render: (row) => String(row.model_spec ?? ''),
  },
  {
    key: 'purchase_qty',
    title: '申购数量',
    width: 110,
    align: 'right',
    render: (row) => renderQuantity(row.purchase_qty, row.unit_name),
  },
  {
    key: 'actual_demand_person',
    title: '实际需求人',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => String(row.actual_demand_person ?? ''),
  },
  {
    key: 'purchase_responsible',
    title: '申购负责人',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => String(row.purchase_responsible ?? ''),
  },
  {
    key: 'salesperson',
    title: '业务员',
    width: 100,
    render: (row) => String(row.salesperson ?? '—'),
  },
  { key: 'subitem_no', title: '子项号', width: 90, render: (row) => String(row.subitem_no ?? '—') },
  {
    key: 'usage',
    title: '用途',
    width: 210,
    ellipsis: { tooltip: true },
    render: (row) => String(row.usage ?? ''),
  },
  { key: 'status', title: '状态', width: 100, render: (row) => renderStatus(row.status) },
  {
    key: 'images',
    title: '图片',
    width: 150,
    render: (row) => h(ImageThumbnails, { images: (row.images ?? []) as FileObject[] }),
  },
]

const columnDefs = computed<ShareColumnDef[]>(() =>
  isRecord.value ? recordColumnDefs : planColumnDefs,
)

/** 展示列：配置了 columns 且非空时按配置过滤注册表，否则展示全部。 */
const visibleKeys = computed<string[]>(() => {
  const all = columnDefs.value.map((def) => def.key)
  const configured = data.value?.columns
  if (!configured || configured.length === 0) return all
  return all.filter((key) => configured.includes(key))
})

const columns = computed<DataTableColumns<ShareRow>>(() =>
  visibleKeys.value.map((key) => {
    const def = columnDefs.value.find((item) => item.key === key)
    if (!def) return { title: key, key, width: 150 }
    return {
      title: def.title,
      key: def.key,
      width: def.width,
      align: def.align,
      ellipsis: def.ellipsis,
      render: def.render,
    }
  }),
)

const rows = computed<ShareRow[]>(() => (data.value?.items ?? []) as ShareRow[])

const scrollX = computed(() =>
  columns.value.reduce((total, column) => {
    const width = Number(column.width ?? column.minWidth ?? 150)
    return total + (Number.isFinite(width) ? width : 150)
  }, 0),
)

const rowKey = (row: ShareRow) => String(isRecord.value ? row.line_id : row.id)

onMounted(async () => {
  const token = String(route.params.token ?? '')
  if (!token) {
    error.value = '分享链接无效'
    loading.value = false
    return
  }
  try {
    data.value = await shareApi.getShare(token)
  } catch (err) {
    error.value = err instanceof AppError ? err.message : '链接不存在或已失效'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="share-page">
    <div class="share-shell">
      <header class="share-header">
        <div class="share-brand">
          <span class="brand-dot" aria-hidden="true" />
          <span>电气车间备件管理系统</span>
        </div>
        <div class="share-title-row">
          <h1 class="share-title">{{ title }} · 分享查看</h1>
          <n-tag :bordered="false" round type="primary" class="share-type-tag">
            {{ isRecord ? '申购记录' : '申购计划' }}
          </n-tag>
        </div>
        <div class="share-meta">
          <n-tag :bordered="false" size="small" round> 共 {{ data?.item_count ?? 0 }} 条 </n-tag>
          <n-tag :bordered="false" size="small" round type="info">
            分享时间 {{ createdLabel }}
          </n-tag>
          <n-tag
            :bordered="false"
            size="small"
            round
            :type="data?.expires_at ? 'warning' : 'success'"
          >
            {{ data?.expires_at ? `失效时间 ${expiryLabel}` : '永久有效' }}
          </n-tag>
          <n-tag v-if="data?.columns?.length" :bordered="false" size="small" round type="info">
            已展示 {{ data.columns.length }} 列
          </n-tag>
        </div>
      </header>

      <section class="share-table-card">
        <n-spin :show="loading">
          <div v-if="error" class="share-error">
            <n-result status="error" title="无法查看分享" :description="error">
              <template #footer>
                <span class="share-error-hint">链接可能已过期，或已被分享人撤回。</span>
              </template>
            </n-result>
          </div>
          <n-data-table
            v-else-if="data"
            :bordered="false"
            :columns="columns"
            :data="rows"
            :row-key="rowKey"
            :scroll-x="scrollX"
            striped
            size="small"
            class="share-table"
          />
        </n-spin>
      </section>

      <footer class="share-footer">
        <span>电气车间备件管理系统 · 数据仅供参考，请以系统内为准</span>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.share-page {
  min-height: 100vh;
  box-sizing: border-box;
  padding: 32px 20px;
  background: linear-gradient(160deg, #eef3fb 0%, #f6f8fb 40%, #f2f5f9 100%);
  display: flex;
  justify-content: center;
}

.share-shell {
  width: 100%;
  max-width: 1100px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.share-header,
.share-table-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(30, 60, 110, 0.08);
}

.share-header {
  padding: 20px 24px 16px;
}

.share-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #7a8699;
  font-size: 13px;
  margin-bottom: 12px;
}

.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2f6fed, #5aa9ff);
}

.share-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.share-title {
  margin: 0;
  font-size: 22px;
  color: #1f2a3d;
  font-weight: 700;
}

.share-type-tag {
  font-weight: 600;
}

.share-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.share-table-card {
  padding: 8px 12px 12px;
  overflow: hidden;
}

.share-table {
  font-size: 13px;
}

.share-table :deep(.n-data-table-th) {
  background: #f4f7fb;
  color: #344054;
  font-weight: 600;
}

.share-table :deep(.n-data-table-tr:hover) {
  background: #f0f5ff;
}

.cell-name {
  font-weight: 600;
  color: #1f2a3d;
}

.share-error {
  padding: 24px 0;
}

.share-error-hint {
  color: #98a2b3;
  font-size: 13px;
}

.share-footer {
  text-align: center;
  color: #a6b0c0;
  font-size: 12px;
  padding: 8px 0 4px;
}

@media (max-width: 640px) {
  .share-page {
    padding: 16px 10px;
  }

  .share-header {
    padding: 16px;
  }

  .share-title {
    font-size: 18px;
  }
}
</style>
