<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, useDialog, useMessage, type FormInst, type FormRules } from 'naive-ui'
import { useRouter } from 'vue-router'
import { inventoryApi } from '@/api/inventory'
import type { FileObject, StockMaterial, StockMaterialWrite } from '@/api/generated'
import { useDictionaryStore } from '@/stores/dictionaries'
import { useAuthStore } from '@/stores/auth'
import ImageUploader from '@/components/ImageUploader.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import { isDecimalString } from '@/utils/decimal'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const auth = useAuthStore()
const dictionaries = useDictionaryStore()
const rowClickGuard = createTableRowClickGuard()
const loading = ref(false)
const items = ref<StockMaterial[]>([])
const total = ref(0)
const page = ref(1)
const filters = reactive({ keyword: '' })
const showModal = ref(false)
const saving = ref(false)
const deletingId = ref<number | null>(null)
const editing = ref<StockMaterial | null>(null)
const formRef = ref<FormInst | null>(null)
const images = ref<FileObject[]>([])
const form = reactive<StockMaterialWrite>({
  name: '',
  model_spec: '',
  unit_id: null,
  remark: '',
  image_ids: [],
})
const policy = reactive({
  minimum_qty: '0',
  enabled: true,
  version: undefined as number | undefined,
})
const rules: FormRules = {
  name: { required: true, message: '请输入物资名称' },
  model_spec: { required: true, message: '请输入型号规格；无型号时填写“无”' },
  unit_id: { type: 'number', required: true, message: '请选择单位' },
}

const columns = preventTableColumnCompression<StockMaterial>([
  {
    title: '物资名称',
    key: 'name',
    width: tableColumnWidths.name,
    render: (row) => row.name,
  },
  {
    title: '型号规格',
    key: 'model_spec',
    width: tableColumnWidths.model,
    ellipsis: { tooltip: true },
  },
  { title: '单位', key: 'unit_name', width: tableColumnWidths.unit },
  { title: '当前库存', key: 'current_qty', width: tableColumnWidths.quantity },
  {
    title: '最低库存',
    key: 'minimum_qty',
    width: tableColumnWidths.quantity,
    render: (row) => row.replenishment_policy?.minimum_qty ?? '未配置',
  },
  {
    title: '档案状态',
    key: 'record_status',
    width: tableColumnWidths.status,
    render: (row) =>
      row.has_operation_records
        ? h(NTag, { size: 'small' }, { default: () => '已有操作记录' })
        : h(NTag, { size: 'small', type: 'success' }, { default: () => '可删除' }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 170,
    render: (row) => {
      if (!auth.can('warehouse:write')) return '—'
      const actions = [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
      ]
      if (!row.has_operation_records) {
        actions.push(
          h(
            NButton,
            {
              size: 'small',
              type: 'error',
              secondary: true,
              loading: deletingId.value === row.id,
              onClick: () => confirmDelete(row),
            },
            { default: () => '删除' },
          ),
        )
      }
      return h('div', { class: 'action-row' }, actions)
    },
  },
])
const tableScrollX = getTableScrollX(columns)

async function load() {
  loading.value = true
  try {
    const data = await inventoryApi.materials({
      page: page.value,
      page_size: 20,
      keyword: filters.keyword.trim() || undefined,
    })
    items.value = data.items
    total.value = data.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : '物资档案加载失败')
  } finally {
    loading.value = false
  }
}

function query() {
  page.value = 1
  void load()
}

function resetFilters() {
  filters.keyword = ''
  query()
}

function resetForm() {
  Object.assign(form, { name: '', model_spec: '', unit_id: null, remark: '', image_ids: [] })
  Object.assign(policy, { minimum_qty: '0', enabled: true, version: undefined })
  images.value = []
  editing.value = null
}

function openCreate() {
  resetForm()
  showModal.value = true
}

function openEdit(row: StockMaterial) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    model_spec: row.model_spec,
    unit_id: row.unit_id,
    remark: row.remark || '',
    image_ids: row.images.map((image) => image.id),
    version: row.version,
  })
  Object.assign(policy, {
    minimum_qty: row.replenishment_policy?.minimum_qty ?? '0',
    enabled: row.replenishment_policy?.enabled ?? true,
    version: row.replenishment_policy?.version,
  })
  images.value = [...row.images]
  showModal.value = true
}

async function save() {
  await formRef.value?.validate()
  if (!isDecimalString(policy.minimum_qty, 1, true)) {
    message.error('最低库存必须为非负数，且最多 1 位小数')
    return
  }
  saving.value = true
  try {
    form.image_ids = images.value.map((image) => image.id)
    const saved = editing.value
      ? await inventoryApi.updateMaterial(editing.value.id, form)
      : await inventoryApi.createMaterial(form)
    await inventoryApi.savePolicy(saved.id, {
      minimum_qty: policy.minimum_qty,
      enabled: policy.enabled,
      version: policy.version,
    })
    message.success('保存成功')
    showModal.value = false
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

function confirmDelete(row: StockMaterial) {
  dialog.warning({
    title: '确认删除物资档案',
    content: `确定删除“${row.name}（${row.model_spec}）”吗？删除后无法恢复。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      deletingId.value = row.id
      try {
        await inventoryApi.deleteMaterial(row.id, row.version)
        message.success('物资档案已删除')
        if (items.value.length === 1 && page.value > 1) page.value -= 1
        await load()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '删除失败')
        return false
      } finally {
        deletingId.value = null
      }
      return true
    },
  })
}

function rowProps(row: StockMaterial) {
  return {
    style: 'cursor: pointer',
    onMousedown: rowClickGuard.onMouseDown,
    onClick: (event: MouseEvent) => {
      if (!rowClickGuard.shouldIgnore(event)) {
        void router.push({ name: 'stock-material-detail', params: { id: row.id } })
      }
    },
  }
}

onMounted(() => {
  void dictionaries.load()
  void load()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">物资档案</h1>
      </div>
      <n-button v-if="auth.can('warehouse:write')" type="primary" @click="openCreate">
        新建物资
      </n-button>
    </div>

    <n-card class="filter-card" :bordered="false">
      <div class="filter-heading">
        <div>
          <div class="filter-title">筛选条件</div>
          <div class="filter-hint">名称和型号支持使用 | 分隔多个关键词，按 OR 查询</div>
        </div>
      </div>
      <div class="warehouse-filter-grid single-column">
        <label class="filter-field">
          <span>名称或型号规格</span>
          <n-input
            v-model:value="filters.keyword"
            clearable
            placeholder="输入物资名称或型号规格"
            @keyup.enter="query"
          />
        </label>
      </div>
      <div class="filter-actions">
        <n-button @click="resetFilters">重置</n-button>
        <n-button type="primary" :loading="loading" @click="query">查询</n-button>
      </div>
    </n-card>

    <n-card class="data-card" :bordered="false">
      <n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-props="rowProps"
        :scroll-x="tableScrollX"
        :row-key="(row: StockMaterial) => row.id"
      />
      <div class="pagination-bar">
        <n-pagination v-model:page="page" :item-count="total" :page-size="20" @update:page="load" />
      </div>
    </n-card>

    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="editing ? '编辑二级库物资' : '新建二级库物资'"
      style="width: 720px"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <div class="form-grid">
          <n-form-item label="物资名称" path="name">
            <n-input v-model:value="form.name" maxlength="128" />
          </n-form-item>
          <n-form-item label="型号规格" path="model_spec">
            <n-input
              v-model:value="form.model_spec"
              maxlength="255"
              placeholder="无型号时填写“无”"
            />
          </n-form-item>
          <n-form-item label="计量单位" path="unit_id">
            <n-select v-model:value="form.unit_id" :options="dictionaries.unitOptions" />
          </n-form-item>
        </div>
        <n-divider title-placement="left">低库存预警</n-divider>
        <div class="form-grid policy-grid">
          <n-form-item label="最低库存">
            <QuantityInput v-model:value="policy.minimum_qty" />
          </n-form-item>
          <n-form-item label="预警状态">
            <div class="switch-field">
              <n-switch v-model:value="policy.enabled" />
              <span>{{ policy.enabled ? '已启用' : '已停用' }}</span>
            </div>
          </n-form-item>
        </div>
        <n-form-item label="备注">
          <n-input v-model:value="form.remark" type="textarea" maxlength="1000" show-count />
        </n-form-item>
        <n-form-item label="图片附件"><ImageUploader v-model:files="images" /></n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.filter-heading,
.filter-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.filter-heading {
  margin-bottom: 18px;
}

.filter-hint {
  margin-top: 4px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.warehouse-filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.warehouse-filter-grid.single-column {
  grid-template-columns: minmax(260px, 520px);
}

.filter-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 7px;
}

.filter-field > span {
  color: #4b5565;
  font-size: 13px;
  font-weight: 500;
}

.filter-actions {
  justify-content: flex-end;
  margin-top: 20px;
}

.switch-field {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 10px;
}

.policy-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (max-width: 760px) {
  .warehouse-filter-grid,
  .warehouse-filter-grid.single-column,
  .policy-grid {
    grid-template-columns: 1fr;
  }
}
</style>
