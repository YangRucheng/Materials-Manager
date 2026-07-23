<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { type DataTableBaseColumn, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import type { PurchaseMaterial } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import ColumnVisibilityPicker from '@/components/ColumnVisibilityPicker.vue'
import { formatDate, formatShanghaiTime } from '@/utils/time'
import { downloadBlob } from '@/utils/download'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'

const router = useRouter()
const dialog = useDialog()
const message = useMessage()
const rowClickGuard = createTableRowClickGuard()
const items = ref<PurchaseMaterial[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const exporting = ref(false)
type UncodedColumnKey = 'plan_no' | 'plan_date' | 'name' | 'model_spec' | 'unit_name' | 'created_at'

const availableColumns: Array<{
  key: UncodedColumnKey
  label: string
  column: DataTableBaseColumn<PurchaseMaterial>
}> = [
  {
    key: 'plan_no',
    label: '计划 ID',
    column: { title: '计划 ID', key: 'plan_no', width: 175 },
  },
  {
    key: 'plan_date',
    label: '需求日期',
    column: {
      title: '需求日期',
      key: 'plan_date',
      width: 110,
      render: (row) => formatDate(row.plan_date),
    },
  },
  {
    key: 'name',
    label: '物资名称',
    column: {
      title: '物资名称',
      key: 'name',
      render: (row) => h('strong', row.name),
    },
  },
  {
    key: 'model_spec',
    label: '型号规格',
    column: { title: '型号规格', key: 'model_spec' },
  },
  {
    key: 'unit_name',
    label: '单位',
    column: { title: '单位', key: 'unit_name', width: 80 },
  },
  {
    key: 'created_at',
    label: '创建时间',
    column: {
      title: '创建时间',
      key: 'created_at',
      width: 170,
      render: (row) => formatShanghaiTime(row.created_at),
    },
  },
]
const visibleColumnKeys = ref<UncodedColumnKey[]>(availableColumns.map((item) => item.key))
const fieldOptions = availableColumns.map((item) => ({ label: item.label, value: item.key }))
const columns = computed<DataTableColumns<PurchaseMaterial>>(() =>
  availableColumns
    .filter((item) => visibleColumnKeys.value.includes(item.key))
    .map((item) => item.column),
)
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
        title: '打开申购计划详情',
        content: `确认打开“${row.name}”对应的申购计划详情吗？`,
        positiveText: '打开',
        negativeText: '取消',
        onPositiveClick: () => router.push(`/procurement/materials/${row.id}`),
      })
    },
  }
}

async function load() {
  loading.value = true
  try {
    const data = await procurementApi.uncodedMaterials({
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function changePageSize() {
  page.value = 1
  void load()
}

async function exportExcel() {
  exporting.value = true
  try {
    const content = await procurementApi.exportUncodedMaterials()
    downloadBlob(content, '物料编码申请表.xlsx')
    message.success('物料编码申请表已导出')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(load)
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
        <n-button :loading="exporting" :disabled="!total" @click="exportExcel">
          导出 Excel
        </n-button>
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
      />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :item-count="total"
          :page-sizes="[10, 20, 50, 100, 200]"
          show-size-picker
          @update:page="load"
          @update:page-size="changePageSize"
        />
      </div>
    </n-card>
  </div>
</template>
