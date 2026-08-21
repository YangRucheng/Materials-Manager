<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import type { DataTableColumns } from 'naive-ui'
import type { FileObject, PurchaseMaterial, PurchaseRecord, SharePublicView } from '@/api/generated'
import { shareApi } from '@/api/share'
import { AppError } from '@/api/client'
import ImageThumbnails from '@/components/ImageThumbnails.vue'
import { formatDate, formatShanghaiTime } from '@/utils/time'

const route = useRoute()

const loading = ref(true)
const error = ref('')
const data = ref<SharePublicView | null>(null)

const title = computed(() =>
  data.value?.share_type === 'purchase_record' ? '申购记录' : '申购计划',
)
const createdLabel = computed(() => (data.value ? formatShanghaiTime(data.value.created_at) : '—'))
const expiryLabel = computed(() => {
  if (!data.value) return '—'
  return data.value.expires_at ? formatShanghaiTime(data.value.expires_at) : '永久有效'
})

const renderQuantity = (
  value: string | number | null | undefined,
  unit: string | null | undefined,
) => (value == null || value === '' ? '—' : `${value}${unit ?? ''}`)

const planColumns: DataTableColumns<PurchaseMaterial> = [
  { title: '计划号', key: 'plan_no', width: 140, fixed: 'left' },
  { title: '需求日期', key: 'plan_date', width: 100, render: (row) => formatDate(row.plan_date) },
  {
    title: '物料编码',
    key: 'material_code',
    width: 130,
    render: (row) => row.material_code || '—',
  },
  { title: '类别', key: 'category', width: 100, render: (row) => row.category || '—' },
  { title: '紧急程度', key: 'urgency', width: 90 },
  { title: '需求部门', key: 'demand_department', width: 150 },
  { title: '名称', key: 'name', width: 160 },
  { title: '型号规格', key: 'model_spec', width: 180 },
  {
    title: '计划数量',
    key: 'planned_qty',
    width: 110,
    render: (row) => renderQuantity(row.planned_qty, row.unit_name),
  },
  { title: '实际需求人', key: 'actual_demand_person', width: 120 },
  { title: '申购负责人', key: 'purchase_responsible', width: 120 },
  { title: '子项号', key: 'subitem_no', width: 90, render: (row) => row.subitem_no || '—' },
  { title: '用途', key: 'usage', width: 200, ellipsis: { tooltip: true } },
  {
    title: '图片',
    key: 'images',
    width: 150,
    render: (row) => h(ImageThumbnails, { images: row.images as FileObject[] }),
  },
]

const recordColumns: DataTableColumns<PurchaseRecord> = [
  { title: '计划号', key: 'plan_no', width: 140, fixed: 'left' },
  { title: '需求日期', key: 'plan_date', width: 100, render: (row) => formatDate(row.plan_date) },
  {
    title: '申购单号',
    key: 'purchase_order_no',
    width: 130,
    render: (row) => row.purchase_order_no || '—',
  },
  { title: '追溯号', key: 'trace_no', width: 130, render: (row) => row.trace_no || '—' },
  { title: '类别', key: 'category', width: 100, render: (row) => row.category || '—' },
  { title: '需求部门', key: 'demand_department', width: 150 },
  { title: '物资名称', key: 'material_name', width: 160 },
  { title: '型号规格', key: 'model_spec', width: 180 },
  {
    title: '申购数量',
    key: 'purchase_qty',
    width: 110,
    render: (row) => renderQuantity(row.purchase_qty, row.unit_name),
  },
  { title: '实际需求人', key: 'actual_demand_person', width: 120 },
  { title: '申购负责人', key: 'purchase_responsible', width: 120 },
  { title: '业务员', key: 'salesperson', width: 100, render: (row) => row.salesperson || '—' },
  { title: '状态', key: 'status', width: 100 },
  { title: '子项号', key: 'subitem_no', width: 90, render: (row) => row.subitem_no || '—' },
  { title: '用途', key: 'usage', width: 200, ellipsis: { tooltip: true } },
  {
    title: '图片',
    key: 'images',
    width: 150,
    render: (row) => h(ImageThumbnails, { images: row.images as FileObject[] }),
  },
]

const columns = computed<DataTableColumns<PurchaseMaterial | PurchaseRecord>>(
  () =>
    (data.value?.share_type === 'purchase_record'
      ? recordColumns
      : planColumns) as DataTableColumns<PurchaseMaterial | PurchaseRecord>,
)
const rows = computed<Array<PurchaseMaterial | PurchaseRecord>>(
  () => (data.value?.items ?? []) as Array<PurchaseMaterial | PurchaseRecord>,
)

const rowKey = (row: PurchaseMaterial | PurchaseRecord) => ('line_id' in row ? row.line_id : row.id)

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
    <header class="share-header">
      <h1 class="share-title">{{ title }} · 分享查看</h1>
      <p class="share-subtitle">
        共 {{ data?.item_count ?? 0 }} 条 · 分享时间 {{ createdLabel }} · 失效时间 {{ expiryLabel }}
      </p>
    </header>

    <n-spin :show="loading" style="min-height: 200px">
      <n-result v-if="error" status="error" title="无法查看分享" :description="error" />
      <template v-else-if="data">
        <n-data-table
          :bordered="false"
          :columns="columns"
          :data="rows"
          :row-key="rowKey"
          :scroll-x="1600"
          size="small"
        />
      </template>
    </n-spin>

    <footer class="share-footer">
      <span>电气车间备件管理系统</span>
    </footer>
  </div>
</template>

<style scoped>
.share-page {
  min-height: 100vh;
  background: #f5f7fa;
  padding: 24px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.share-header {
  background: #fff;
  border-radius: 8px;
  padding: 20px 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.share-title {
  margin: 0 0 8px;
  font-size: 20px;
  color: #333;
}

.share-subtitle {
  margin: 0;
  color: #999;
  font-size: 13px;
}

.share-footer {
  margin-top: auto;
  text-align: center;
  color: #bbb;
  font-size: 12px;
  padding: 12px 0;
}
</style>
