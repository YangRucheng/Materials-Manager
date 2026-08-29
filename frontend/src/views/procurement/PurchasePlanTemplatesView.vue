<script setup lang="ts">
import { computed, h, reactive, ref } from 'vue'
import {
  type DataTableColumns,
  type FormInst,
  type FormRules,
  useDialog,
  useMessage,
} from 'naive-ui'
import type { FileObject, MaterialCodeLibrary, PurchasePlanTemplate } from '@/api/generated'
import { purchasePlanTemplateApi } from '@/api/purchasePlanTemplates'
import { useAuthStore } from '@/stores/auth'
import FilterExpandButton from '@/components/FilterExpandButton.vue'
import ImageUploader from '@/components/ImageUploader.vue'
import MaterialCodeSelector from '@/components/MaterialCodeSelector.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import {
  defaultDemandDepartment,
  defaultPurchaseUrgency,
  purchaseCategoryOptions,
  purchaseUrgencyOptions,
} from '@/constants/purchase'
import {
  getTableScrollX,
  preventTableColumnCompression,
  tableColumnWidths,
} from '@/constants/table'
import { usePagedTable } from '@/composables/usePagedTable'
import { useShiftWheelHorizontalScroll } from '@/composables/useShiftWheelHorizontalScroll'
import { createTableRowClickGuard } from '@/utils/tableRowNavigation'
import { formatShanghaiTime } from '@/utils/time'
import { routeQueryString } from '@/utils/routeQuery'

const auth = useAuthStore()
const message = useMessage()
const dialog = useDialog()
const rowClickGuard = createTableRowClickGuard()
const filterExpanded = ref(false)

interface TemplateFilters {
  name: string
  model_spec: string
  actual_demand_person: string | null
  purchase_responsible: string | null
  category: string | null
}
const {
  items,
  total,
  page,
  pageSize,
  loading,
  filters,
  load,
  query,
  changePage,
  changePageSize,
  resetFilters,
} = usePagedTable<PurchasePlanTemplate, TemplateFilters>({
  fetch: (f, pager) =>
    purchasePlanTemplateApi.templates({
      page: pager.page,
      page_size: pager.page_size,
      name: f.name.trim() || undefined,
      model_spec: f.model_spec.trim() || undefined,
      actual_demand_person: f.actual_demand_person?.trim() || undefined,
      purchase_responsible: f.purchase_responsible?.trim() || undefined,
      category: f.category || undefined,
    }),
  initialFilters: () => ({
    name: '',
    model_spec: '',
    actual_demand_person: null,
    purchase_responsible: null,
    category: null,
  }),
  urlSync: {
    routeName: 'purchase-plan-templates',
    fromQuery: (route) => ({
      name: routeQueryString(route.query.name),
      model_spec: routeQueryString(route.query.model_spec),
      actual_demand_person: routeQueryString(route.query.actual_demand_person) || null,
      purchase_responsible: routeQueryString(route.query.purchase_responsible) || null,
      category: routeQueryString(route.query.category) || null,
    }),
    toQuery: (f) => ({
      name: f.name,
      model_spec: f.model_spec,
      actual_demand_person: f.actual_demand_person || undefined,
      purchase_responsible: f.purchase_responsible || undefined,
      category: f.category || undefined,
    }),
  },
})

const filterOptions = ref<{
  actual_demand_persons: string[]
  purchase_responsibles: string[]
  categories: string[]
}>({ actual_demand_persons: [], purchase_responsibles: [], categories: [] })
const actualDemandPersonOptions = computed(() =>
  filterOptions.value.actual_demand_persons.map((value) => ({ label: value, value })),
)
const purchaseResponsibleOptions = computed(() =>
  filterOptions.value.purchase_responsibles.map((value) => ({ label: value, value })),
)
const categoryOptions = computed(() => {
  const values = new Set([
    ...purchaseCategoryOptions.map((option) => option.value),
    ...filterOptions.value.categories,
  ])
  return [...values].map((value) => ({ label: value, value }))
})
const activeFilterCount = computed(
  () =>
    [
      filters.name.trim(),
      filters.model_spec.trim(),
      filters.actual_demand_person,
      filters.purchase_responsible,
      filters.category,
    ].filter(Boolean).length,
)

async function loadFilterOptions() {
  try {
    filterOptions.value = await purchasePlanTemplateApi.templateFilterOptions()
  } catch {
    // 筛选下拉加载失败不阻断页面
  }
}

const show = ref(false)
const editing = ref<PurchasePlanTemplate | null>(null)
const saving = ref(false)
const deleting = ref(false)
const generating = ref(false)
const tableAreaRef = ref<HTMLElement | null>(null)
const formRef = ref<FormInst | null>(null)
const images = ref<FileObject[]>([])
const createAdvancedSections = ref<string[]>([])

const form = reactive({
  material_code: '',
  category: '',
  urgency: defaultPurchaseUrgency,
  demand_department: defaultDemandDepartment,
  name: '',
  model_spec: '',
  unit_name: '',
  actual_demand_person: '',
  purchase_responsible: '',
  planned_qty: '',
  usage: '',
  subitem_no: '',
  stock_material_id: undefined as number | undefined,
  remark: '',
})
const rules: FormRules = {
  name: { required: true, message: '请输入名称' },
  model_spec: { required: true, message: '请输入型号规格' },
  actual_demand_person: { required: true, message: '请输入提报员工' },
  purchase_responsible: { required: true, message: '请输入实际需求人' },
  planned_qty: [
    { required: true, message: '请输入计划数量' },
    {
      validator: () => Boolean(form.unit_name.trim()),
      message: '请输入计量单位',
      trigger: ['blur', 'change'],
    },
  ],
  usage: { required: true, message: '请输入用途' },
}

useShiftWheelHorizontalScroll(tableAreaRef)

const columns = computed<DataTableColumns<PurchasePlanTemplate>>(() =>
  preventTableColumnCompression<PurchasePlanTemplate>([
    {
      title: '名称',
      key: 'name',
      width: tableColumnWidths.name,
      render: (row) => h('strong', row.name),
    },
    {
      title: '型号规格',
      key: 'model_spec',
      width: tableColumnWidths.model,
      ellipsis: { tooltip: true },
    },
    {
      title: '类别',
      key: 'category',
      width: tableColumnWidths.status,
      render: (row) => row.category || '-',
    },
    {
      title: '计划数量 / 单位',
      key: 'planned_qty',
      width: tableColumnWidths.quantity + tableColumnWidths.unit,
      render: (row) => `${String(row.planned_qty)} ${row.unit_name}`,
    },
    {
      title: '用途',
      key: 'usage',
      width: tableColumnWidths.text,
      ellipsis: { tooltip: true },
    },
    {
      title: '提报员工',
      key: 'actual_demand_person',
      width: tableColumnWidths.person,
    },
    {
      title: '实际需求人',
      key: 'purchase_responsible',
      width: tableColumnWidths.person,
    },
    {
      title: '创建时间',
      key: 'created_at',
      width: tableColumnWidths.datetime,
      render: (row) => formatShanghaiTime(row.created_at),
    },
  ]),
)
const tableScrollX = computed(() => getTableScrollX(columns.value))

function rowProps(row: PurchasePlanTemplate) {
  const interactive = auth.can('purchase:write')
  return {
    style: interactive ? 'cursor: pointer' : undefined,
    onMousedown: rowClickGuard.onMouseDown,
    onClick: (event: MouseEvent) => {
      if (!interactive) return
      if (rowClickGuard.shouldIgnore(event)) return
      openEdit(row)
    },
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    material_code: '',
    category: '',
    urgency: defaultPurchaseUrgency,
    demand_department: defaultDemandDepartment,
    name: '',
    model_spec: '',
    unit_name: '',
    actual_demand_person: '',
    purchase_responsible: '',
    planned_qty: '',
    usage: '',
    subitem_no: '',
    stock_material_id: undefined,
    remark: '',
  })
  images.value = []
  createAdvancedSections.value = []
  show.value = true
}
function openEdit(row: PurchasePlanTemplate) {
  editing.value = row
  Object.assign(form, {
    material_code: row.material_code || '',
    category: row.category || '',
    urgency: row.urgency,
    demand_department: row.demand_department,
    name: row.name,
    model_spec: row.model_spec,
    unit_name: row.unit_name,
    actual_demand_person: row.actual_demand_person,
    purchase_responsible: row.purchase_responsible,
    planned_qty: row.planned_qty,
    usage: row.usage,
    subitem_no: row.subitem_no || '',
    stock_material_id: row.stock_material_id ?? undefined,
    remark: row.remark || '',
  })
  images.value = [...row.images]
  createAdvancedSections.value = []
  show.value = true
}
function applyMaterialCode(item: MaterialCodeLibrary) {
  form.material_code = item.material_code
  if (item.name?.trim()) form.name = item.name
  if (item.model_spec?.trim()) form.model_spec = item.model_spec
  form.unit_name = item.unit_name
}
async function save() {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload = {
      ...form,
      subitem_no: form.subitem_no?.trim() || undefined,
      image_ids: images.value.map((image) => image.id),
    }
    if (editing.value) {
      await purchasePlanTemplateApi.updateTemplate(editing.value.id, {
        ...payload,
        version: editing.value.version,
      })
      message.success('周期性计划已保存')
    } else {
      await purchasePlanTemplateApi.createTemplate(payload)
      message.success('周期性计划已创建')
    }
    show.value = false
    editing.value = null
    page.value = 1
    await Promise.all([load(), loadFilterOptions()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}
async function deleteTemplate() {
  const target = editing.value
  if (!target) return
  deleting.value = true
  try {
    await purchasePlanTemplateApi.deleteTemplate(target.id, target.version)
    message.success('周期性计划已删除')
    show.value = false
    editing.value = null
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    await Promise.all([load(), loadFilterOptions()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '删除失败')
  } finally {
    deleting.value = false
  }
}
function confirmDelete(row: PurchasePlanTemplate) {
  dialog.warning({
    draggable: true,
    title: '删除周期性计划',
    content: `确认删除“${row.name}”这条周期性计划吗？删除后不可恢复（不影响已生成的申购计划）。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: () => {
      editing.value = row
      void deleteTemplate()
    },
  })
}
async function generatePlan(row: PurchasePlanTemplate) {
  generating.value = true
  try {
    const material = await purchasePlanTemplateApi.generatePurchasePlan(row.id)
    message.success(`已生成申购计划「${material.plan_no}」，需求日期为今天`)
    await Promise.all([load(), loadFilterOptions()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '生成失败')
  } finally {
    generating.value = false
  }
}
function confirmGenerate(row: PurchasePlanTemplate) {
  dialog.info({
    draggable: true,
    title: '生成申购计划',
    content: `将按“${row.name}”模板生成一条需求日期为今天的申购计划（模板本身不会被删除或修改）。确定继续吗？`,
    positiveText: '生成',
    negativeText: '取消',
    onPositiveClick: () => void generatePlan(row),
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">周期性计划</h1>
      </div>
      <n-space>
        <n-button v-if="auth.can('purchase:write')" type="primary" @click="openCreate">
          新建周期性计划
        </n-button>
      </n-space>
    </div>
    <n-card class="filter-card" :bordered="false">
      <div class="filter-heading">
        <div class="filter-title">筛选条件</div>
        <div class="filter-heading-actions">
          <n-tag v-if="activeFilterCount" :bordered="false" round type="success">
            已启用 {{ activeFilterCount }} 项
          </n-tag>
          <FilterExpandButton v-model:expanded="filterExpanded" />
        </div>
      </div>
      <div class="filter-grid">
        <label class="filter-field">
          <span>物资名称</span>
          <n-input
            v-model:value="filters.name"
            placeholder="输入物资名称"
            clearable
            @keyup.enter="query"
          />
        </label>
        <label class="filter-field">
          <span>型号规格</span>
          <n-input
            v-model:value="filters.model_spec"
            placeholder="输入型号规格"
            clearable
            @keyup.enter="query"
          />
        </label>
        <div class="filter-extras-fields" :class="{ 'filter-extras-open': filterExpanded }">
          <label class="filter-field">
            <span>提报员工</span>
            <n-select
              v-model:value="filters.actual_demand_person"
              :options="actualDemandPersonOptions"
              placeholder="选择或搜索提报员工"
              filterable
              clearable
            />
          </label>
          <label class="filter-field">
            <span>实际需求人</span>
            <n-select
              v-model:value="filters.purchase_responsible"
              :options="purchaseResponsibleOptions"
              placeholder="选择或搜索实际需求人"
              filterable
              clearable
            />
          </label>
          <label class="filter-field">
            <span>类别</span>
            <n-select
              v-model:value="filters.category"
              :options="categoryOptions"
              placeholder="选择类别"
              filterable
              clearable
            />
          </label>
        </div>
      </div>
      <div class="filter-extras-actions">
        <div class="filter-actions">
          <div class="filter-action-buttons">
            <n-button @click="resetFilters">重置</n-button>
            <n-button type="primary" @click="query">查询</n-button>
          </div>
        </div>
      </div>
    </n-card>
    <div ref="tableAreaRef" class="template-table-area">
      <n-card class="data-card">
        <n-data-table
          :bordered="false"
          :columns="columns"
          :data="items"
          :loading="loading"
          :remote="true"
          :row-props="rowProps"
          :row-key="(row: PurchasePlanTemplate) => row.id"
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
    <n-modal
      v-model:show="show"
      preset="card"
      draggable
      :title="editing ? '编辑周期性计划' : '新建周期性计划'"
      style="width: min(680px, calc(100vw - 24px))"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
        <div class="form-grid">
          <n-form-item label="物料编码">
            <MaterialCodeSelector
              :model-value="form.material_code || ''"
              :default-name="form.name"
              :default-model-spec="form.model_spec"
              @update:model-value="form.material_code = $event"
              @select="applyMaterialCode"
            />
          </n-form-item>
          <n-form-item label="名称" path="name">
            <n-input v-model:value="form.name" maxlength="128" />
          </n-form-item>
          <n-form-item label="型号规格" path="model_spec">
            <n-input v-model:value="form.model_spec" maxlength="255" />
          </n-form-item>
          <n-form-item label="紧急程度">
            <n-select v-model:value="form.urgency" :options="purchaseUrgencyOptions" />
          </n-form-item>
          <n-form-item label="计划数量 / 计量单位" path="planned_qty">
            <n-input-group>
              <QuantityInput
                v-model:value="form.planned_qty"
                :decimal-places="1"
                class="quantity-input"
              />
              <n-input
                v-model:value="form.unit_name"
                maxlength="32"
                placeholder="计量单位"
                class="quantity-unit-select"
              />
            </n-input-group>
          </n-form-item>
          <n-form-item label="提报员工" path="actual_demand_person">
            <n-input
              v-model:value="form.actual_demand_person"
              maxlength="128"
              placeholder="填写提出需求的员工"
            />
          </n-form-item>
          <n-form-item label="实际需求人" path="purchase_responsible">
            <n-input
              v-model:value="form.purchase_responsible"
              maxlength="128"
              placeholder="填写作为实际需求人的车间负责人"
            />
          </n-form-item>
          <n-form-item label="子项号">
            <n-input v-model:value="form.subitem_no" maxlength="64" placeholder="选填" />
          </n-form-item>
          <n-form-item label="用途" path="usage">
            <n-input v-model:value="form.usage" maxlength="500" />
          </n-form-item>
        </div>
        <n-collapse v-model:expanded-names="createAdvancedSections" class="create-advanced-fields">
          <n-collapse-item name="advanced">
            <template #header>
              <span class="advanced-header">更多设置</span>
            </template>
            <div class="form-grid">
              <n-form-item label="类别">
                <n-select
                  v-model:value="form.category"
                  :options="categoryOptions"
                  filterable
                  clearable
                  placeholder="选择类别"
                />
              </n-form-item>
              <n-form-item label="需求部门">
                <n-input v-model:value="form.demand_department" maxlength="128" />
              </n-form-item>
              <n-form-item label="关联二级库物资">
                <MaterialSelector
                  :value="form.stock_material_id ?? null"
                  @update:value="form.stock_material_id = $event ?? undefined"
                />
              </n-form-item>
            </div>
          </n-collapse-item>
        </n-collapse>
        <n-form-item label="备注"
          ><n-input v-model:value="form.remark" type="textarea" maxlength="1000" show-count
        /></n-form-item>
        <n-form-item label="图片附件"><ImageUploader v-model:files="images" /></n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="space-between">
          <n-space justify="start">
            <n-button
              v-if="editing && auth.can('purchase:write')"
              type="primary"
              secondary
              :loading="generating"
              @click="confirmGenerate(editing)"
            >
              生成申购计划
            </n-button>
            <n-button
              v-if="editing && auth.can('purchase:write')"
              type="error"
              ghost
              :loading="deleting"
              @click="confirmDelete(editing)"
            >
              删除
            </n-button>
          </n-space>
          <n-space justify="end">
            <n-button @click="show = false">取消</n-button>
            <n-button type="primary" :loading="saving" @click="save">保存</n-button>
          </n-space>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.quantity-input {
  flex: 1;
}

.quantity-unit-select {
  width: 160px;
}

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

.create-advanced-fields {
  margin-bottom: 18px;
  overflow: hidden;
  border-radius: 8px;
  background: var(--color-surface-soft);
}

.create-advanced-fields :deep(.n-collapse-item) {
  border-radius: 8px;
}

.create-advanced-fields :deep(.n-collapse-item__header) {
  padding: 10px 12px;
  transition: background-color 0.2s ease;
}

.create-advanced-fields :deep(.n-collapse-item__header:hover) {
  background: #eef2f9;
}

.create-advanced-fields :deep(.n-collapse-item__content-inner) {
  padding: 12px;
}

.advanced-header {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  color: #4b5565;
}

.filter-actions {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-subtle);
}

.filter-action-buttons {
  display: flex;
  flex: none;
  gap: 10px;
}

.filter-action-buttons :deep(.n-button) {
  min-width: 88px;
}

.template-table-area {
  position: relative;
}

@media (max-width: 900px) {
  .filter-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .filter-action-buttons {
    justify-content: flex-end;
  }
}
</style>
