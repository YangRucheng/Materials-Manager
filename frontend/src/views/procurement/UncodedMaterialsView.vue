<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { type DataTableBaseColumn, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { PurchaseMaterial } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import ColumnVisibilityPicker from '@/components/ColumnVisibilityPicker.vue'
import ExportButton from '@/components/ExportButton.vue'
import type { ExportOption } from '@/types/export'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import { formatDate, formatShanghaiTime, toShanghaiDate } from '@/utils/time'
import { downloadBlob } from '@/utils/download'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'
import { defaultPurchasePlanStatus } from '@/constants/purchase'
import { usePagedTable } from '@/composables/usePagedTable'

const router = useRouter()
const dialog = useDialog()
const message = useMessage()
const rowClickGuard = createTableRowClickGuard()
const { items, total, page, pageSize, loading, changePage, changePageSize } = usePagedTable<
  PurchaseMaterial,
  Record<string, never>
>({
  fetch: (_f, pager) =>
    procurementApi.uncodedMaterials({
      page: pager.page,
      page_size: pager.page_size,
      status: defaultPurchasePlanStatus,
    }),
  initialFilters: () => ({}),
})
const exporting = ref(false)
const exportOptions: ExportOption[] = [
  { label: `导出物料编码申请表（共 ${total.value} 条）`, key: 'application' },
]
type UncodedColumnKey = 'plan_date' | 'name' | 'model_spec' | 'unit_name' | 'created_at'

const availableColumns: Array<{
  key: UncodedColumnKey
  label: string
  column: DataTableBaseColumn<PurchaseMaterial>
}> = [
  {
    key: 'plan_date',
    label: '需求日期',
    column: {
      title: '需求日期',
      key: 'plan_date',
      width: tableColumnWidths.date,
      render: (row) => formatDate(row.plan_date),
    },
  },
  {
    key: 'name',
    label: '物资名称',
    column: {
      title: '物资名称',
      key: 'name',
      width: tableColumnWidths.name,
      render: (row) => h('strong', row.name),
    },
  },
  {
    key: 'model_spec',
    label: '型号规格',
    column: {
      title: '型号规格',
      key: 'model_spec',
      width: tableColumnWidths.model,
      ellipsis: { tooltip: true },
    },
  },
  {
    key: 'unit_name',
    label: '计量单位',
    column: { title: '计量单位', key: 'unit_name', width: tableColumnWidths.unit },
  },
  {
    key: 'created_at',
    label: '创建时间',
    column: {
      title: '创建时间',
      key: 'created_at',
      width: tableColumnWidths.datetime,
      render: (row) => formatShanghaiTime(row.created_at),
    },
  },
]
const visibleColumnKeys = ref<UncodedColumnKey[]>(availableColumns.map((item) => item.key))
const fieldOptions = availableColumns.map((item) => ({ label: item.label, value: item.key }))
const columns = computed<DataTableColumns<PurchaseMaterial>>(() =>
  preventTableColumnCompression(
    availableColumns
      .filter((item) => visibleColumnKeys.value.includes(item.key))
      .map((item) => item.column),
  ),
)
const tableScrollX = computed(() => getTableScrollX(columns.value))
function setVisibleColumnKeys(value: string[]) {
  visibleColumnKeys.value = value as UncodedColumnKey[]
}

function rowProps(row: PurchaseMaterial) {
  return {
    style: 'cursor: pointer',
    onMousedown: rowClickGuard.onMouseDown,
    onClick: (event: MouseEvent) => {
      if (rowClickGuard.shouldIgnore(event)) return
      dialog.warning({
        draggable: true,
        title: '打开申购计划详情',
        content: `确认打开“${row.name}”对应的申购计划详情吗？`,
        positiveText: '打开',
        negativeText: '取消',
        onPositiveClick: () => router.push(`/procurement/materials/${row.id}`),
      })
    },
  }
}

async function exportExcel() {
  exporting.value = true
  try {
    const content = await procurementApi.exportUncodedMaterials()
    const date = toShanghaiDate(Date.now()).replace(/-/g, '')
    downloadBlob(content, `物料编码申请表_${date}.xlsx`)
    message.success('物料编码申请表已导出')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

function handleExport(key: string) {
  if (key === 'application') void exportExcel()
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">未编码物资</h1>
      </div>
      <n-space>
        <ColumnVisibilityPicker
          :value="visibleColumnKeys"
          :options="fieldOptions"
          storage-key="procurement.uncoded-materials.visible-columns.v1"
          @update:value="setVisibleColumnKeys"
        />
        <ExportButton
          :options="exportOptions"
          :loading="exporting"
          :disabled="!total"
          @select="handleExport"
        />
      </n-space>
    </div>
    <n-card class="data-card">
      <n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-props="rowProps"
        :row-key="(row: PurchaseMaterial) => row.id"
        :scroll-x="tableScrollX"
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
  </div>
</template>
