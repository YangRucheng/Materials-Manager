<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NTag,
  useMessage,
  type DataTableColumns,
  type FormInst,
  type FormRules,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import type { FileObject, PurchaseMaterial, PurchaseMaterialWrite } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionaries'
import ImageUploader from '@/components/ImageUploader.vue'
import ProjectSubitemSelector from '@/components/ProjectSubitemSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'

const router = useRouter()
const auth = useAuthStore()
const dictionaries = useDictionaryStore()
const message = useMessage()
const items = ref<PurchaseMaterial[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const show = ref(false)
const saving = ref(false)
const formRef = ref<FormInst | null>(null)
const images = ref<FileObject[]>([])
const filters = reactive({ keyword: '', coded: null as boolean | null })
const form = reactive<PurchaseMaterialWrite>({
  material_code: '',
  name: '',
  model_spec: '',
  unit_id: null,
  actual_demand_person: '',
  purchase_responsible: '',
  planned_qty: '',
  usage: '',
  project_subitem_id: undefined,
  remark: '',
  image_ids: [],
})
const rules: FormRules = {
  name: { required: true, message: '请输入名称' },
  model_spec: { required: true, message: '请输入型号规格' },
  unit_id: { type: 'number', required: true, message: '请选择单位' },
  actual_demand_person: { required: true, message: '请输入实际需求人' },
  purchase_responsible: { required: true, message: '请输入申购负责人' },
  planned_qty: { required: true, message: '请输入计划数量' },
  usage: { required: true, message: '请输入用途' },
  project_subitem_id: { type: 'number', required: true, message: '请选择项目子项' },
}
const codeLabels = { UNCODED: '未编码', CODED: '已有编码' }
const columns: DataTableColumns<PurchaseMaterial> = [
  {
    title: '物料编码',
    key: 'material_code',
    width: 140,
    render: (r) =>
      r.material_code || h(NTag, { type: 'warning', size: 'small' }, { default: () => '暂无编码' }),
  },
  {
    title: '名称',
    key: 'name',
    render: (r) =>
      h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: () => router.push(`/procurement/materials/${r.id}`),
        },
        { default: () => r.name },
      ),
  },
  { title: '型号规格', key: 'model_spec' },
  { title: '单位', key: 'unit_name', width: 70 },
  { title: '计划数量', key: 'planned_qty', width: 100 },
  { title: '实际需求人', key: 'actual_demand_person', width: 110 },
  { title: '申购负责人', key: 'purchase_responsible', width: 110 },
  {
    title: '编码状态',
    key: 'code_state',
    width: 100,
    render: (r) =>
      h(
        NTag,
        {
          type: r.code_state === 'CODED' ? 'success' : 'warning',
        },
        { default: () => codeLabels[r.code_state] },
      ),
  },
  {
    title: '关联二级库物资',
    key: 'stock_material_name',
    render: (r) => r.stock_material_name || '—',
  },
  {
    title: '操作',
    key: 'action',
    width: 180,
    render: (r) =>
      h('div', { class: 'action-row' }, [
        h(
          NButton,
          { size: 'small', onClick: () => router.push(`/procurement/materials/${r.id}`) },
          { default: () => '详情' },
        ),
        ...(auth.can('purchase:write') && r.code_state === 'UNCODED'
          ? [
              h(
                NButton,
                {
                  size: 'small',
                  type: 'primary',
                  onClick: () => router.push(`/procurement/materials/${r.id}`),
                },
                { default: () => '补充编码' },
              ),
            ]
          : []),
      ]),
  },
]
async function load() {
  loading.value = true
  try {
    const d = await procurementApi.materials({
      page: page.value,
      page_size: 20,
      moved: false,
      ...filters,
    })
    items.value = d.items
    total.value = d.total
  } finally {
    loading.value = false
  }
}
function query() {
  page.value = 1
  void load()
}
function openCreate() {
  Object.assign(form, {
    material_code: '',
    name: '',
    model_spec: '',
    unit_id: null,
    actual_demand_person: '',
    purchase_responsible: '',
    planned_qty: '',
    usage: '',
    project_subitem_id: undefined,
    remark: '',
    image_ids: [],
  })
  images.value = []
  show.value = true
}
async function save() {
  await formRef.value?.validate()
  saving.value = true
  try {
    form.image_ids = images.value.map((x) => x.id)
    const created = await procurementApi.createMaterial(form)
    message.success('申购计划已创建')
    show.value = false
    await router.push(`/procurement/materials/${created.id}`)
  } catch (e) {
    message.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    saving.value = false
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
        <h1 class="page-title">申购计划</h1>
        <p class="page-subtitle">计划阶段确定物资、数量、用途和项目，物料编码可暂时为空</p>
      </div>
      <n-button v-if="auth.can('purchase:write')" type="primary" @click="openCreate"
        >新建申购计划</n-button
      >
    </div>
    <n-card
      ><div class="filter-bar">
        <n-input
          v-model:value="filters.keyword"
          placeholder="编码、名称或规格"
          clearable
          style="width: 240px"
        /><n-select
          v-model:value="filters.coded"
          clearable
          :options="[
            { value: false, label: '未编码' },
            { value: true, label: '已有编码' },
          ]"
          placeholder="编码状态"
          style="width: 140px"
        /><n-button type="primary" @click="query">查询</n-button>
      </div></n-card
    ><n-card
      ><n-data-table
        :bordered="false"
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(r: PurchaseMaterial) => r.id" />
      <div class="pagination-bar">
        <n-pagination
          v-model:page="page"
          :page-size="20"
          :item-count="total"
          @update:page="load"
        /></div
    ></n-card>
    <n-modal
      v-model:show="show"
      preset="card"
      title="新建申购计划"
      style="width: 680px"
      :mask-closable="false"
      ><n-form ref="formRef" :model="form" :rules="rules" label-placement="top"
        ><div class="form-grid">
          <n-form-item label="物料编码（已有时填写）"
            ><n-input
              v-model:value="form.material_code"
              maxlength="64"
              placeholder="没有编码可留空" /></n-form-item
          ><n-form-item label="名称" path="name"
            ><n-input v-model:value="form.name" maxlength="128" /></n-form-item
          ><n-form-item label="型号规格" path="model_spec"
            ><n-input v-model:value="form.model_spec" maxlength="255" /></n-form-item
          ><n-form-item label="计量单位" path="unit_id"
            ><n-select
              v-model:value="form.unit_id"
              :options="dictionaries.unitOptions" /></n-form-item
          ><n-form-item label="实际需求人" path="actual_demand_person"
            ><n-input
              v-model:value="form.actual_demand_person"
              maxlength="128"
              placeholder="填写提出实际需求的员工" /></n-form-item
          ><n-form-item label="申购负责人" path="purchase_responsible"
            ><n-input v-model:value="form.purchase_responsible" maxlength="128"
          /></n-form-item>
          <n-form-item label="计划数量" path="planned_qty"
            ><QuantityInput v-model:value="form.planned_qty" :decimal-places="1"
          /></n-form-item>
          <n-form-item label="项目子项" path="project_subitem_id"
            ><ProjectSubitemSelector
              :value="form.project_subitem_id ?? null"
              @update:value="form.project_subitem_id = $event ?? undefined"
          /></n-form-item>
        </div>
        <n-form-item label="用途" path="usage"
          ><n-input v-model:value="form.usage" maxlength="500"
        /></n-form-item>
        <n-form-item label="备注"
          ><n-input
            v-model:value="form.remark"
            type="textarea"
            maxlength="1000"
            show-count /></n-form-item
        ><n-form-item label="图片"><ImageUploader v-model:files="images" /></n-form-item></n-form
      ><template #footer
        ><n-space justify="end"
          ><n-button @click="show = false">取消</n-button
          ><n-button type="primary" :loading="saving" @click="save">保存</n-button></n-space
        ></template
      ></n-modal
    >
  </div>
</template>
