<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import type { PurchaseMaterial, PurchaseRequest, PurchaseRequestWrite } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import PurchaseMaterialSelector from '@/components/PurchaseMaterialSelector.vue'
import ProjectSubitemSelector from '@/components/ProjectSubitemSelector.vue'
import QuantityInput from '@/components/QuantityInput.vue'
import { isDecimalString } from '@/utils/decimal'
import { defaultPurchaseRequestNo, findUncodedLineNumbers } from '@/utils/purchase'

interface LineModel {
  id?: number
  purchase_material_id: number | null
  requested_qty: string
  usage: string
  project_subitem_id: number | null
  material?: PurchaseMaterial
}
const route = useRoute()
const router = useRouter()
const message = useMessage()
const request = ref<PurchaseRequest | null>(null)
const saving = ref(false)
const loading = ref(false)
const model = reactive<{ request_no: string; remark: string; lines: LineModel[] }>({
  request_no: defaultPurchaseRequestNo(),
  remark: '',
  lines: [{ purchase_material_id: null, requested_qty: '', usage: '', project_subitem_id: null }],
})
const uncodedLineNumbers = computed(() => findUncodedLineNumbers(model.lines))
const responsibleIds = computed(() => [
  ...new Set(
    model.lines
      .map((line) => line.material?.purchase_responsible_id)
      .filter((id): id is number => id !== undefined),
  ),
])
const applicantName = computed(() => {
  const names = [
    ...new Set(
      model.lines
        .map((line) => line.material?.purchase_responsible_name)
        .filter((name): name is string => Boolean(name)),
    ),
  ]
  return names.length === 1 ? names[0] : ''
})
const uncodedLines = computed(() =>
  model.lines
    .map((x, i) => ({ line: x, index: i + 1 }))
    .filter((_, i) => uncodedLineNumbers.value.includes(i + 1)),
)
function add() {
  model.lines.push({
    purchase_material_id: null,
    requested_qty: '',
    usage: '',
    project_subitem_id: null,
  })
}
function remove(i: number) {
  model.lines.splice(i, 1)
}
function selectMaterial(i: number, material?: PurchaseMaterial) {
  model.lines[i].material = material
}
function validate() {
  if (!model.request_no.trim()) return '请填写请购单号'
  if (!model.lines.length) return '至少添加一行明细'
  if (responsibleIds.value.length > 1) return '同一请购单只能选择同一申购负责人的计划'
  const bad = model.lines.find(
    (x) =>
      !x.purchase_material_id ||
      !isDecimalString(x.requested_qty, 1) ||
      !x.usage.trim() ||
      !x.project_subitem_id,
  )
  return bad ? '请完整填写每行物资、数量、用途和项目子项' : null
}
function payload(): PurchaseRequestWrite {
  return {
    request_no: model.request_no,
    remark: model.remark,
    version: request.value?.version,
    lines: model.lines.map((x) => ({
      id: x.id,
      purchase_material_id: x.purchase_material_id,
      requested_qty: x.requested_qty,
      usage: x.usage,
      project_subitem_id: x.project_subitem_id,
    })),
  }
}
async function saveDraft() {
  const err = validate()
  if (err) {
    message.error(err)
    return null
  }
  saving.value = true
  try {
    const saved = request.value
      ? await procurementApi.updateRequest(request.value.id, payload())
      : await procurementApi.createRequest(payload())
    request.value = saved
    message.success('草稿已保存')
    return saved
  } catch (e) {
    message.error(e instanceof Error ? e.message : '保存失败')
    return null
  } finally {
    saving.value = false
  }
}
async function saveAndSubmit() {
  const saved = await saveDraft()
  if (!saved) return
  if (uncodedLines.value.length) {
    message.error(
      `第 ${uncodedLines.value.map((x) => x.index).join('、')} 行物资没有编码，请先申请编码`,
    )
    return
  }
  try {
    await procurementApi.requestAction(saved.id, 'submit')
    message.success('请购单已提交')
    await router.replace(`/procurement/requests/${saved.id}`)
  } catch (e) {
    message.error(e instanceof Error ? e.message : '提交失败')
  }
}
async function goCompleteCode(line: LineModel) {
  if (!line.material) return
  await router.push(`/procurement/materials/${line.material.id}`)
}
async function loadExisting() {
  const id = Number(route.query.edit)
  if (!id) return
  loading.value = true
  try {
    request.value = await procurementApi.request(id)
    model.request_no = request.value.request_no
    model.remark = request.value.remark || ''
    const materials = await Promise.all(
      request.value.lines.map((line) => procurementApi.material(line.purchase_material_id)),
    )
    model.lines = request.value.lines.map((x) => ({
      id: x.id,
      purchase_material_id: x.purchase_material_id,
      requested_qty: x.requested_qty,
      usage: x.usage,
      project_subitem_id: x.project_subitem_id,
      material: materials.find((material) => material.id === x.purchase_material_id),
    }))
  } finally {
    loading.value = false
  }
}
onMounted(() => {
  void loadExisting()
})
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="page-header">
      <div>
        <n-button text @click="router.back()">← 返回请购单</n-button>
        <h1 class="page-title">{{ request ? '编辑请购草稿' : '新建请购' }}</h1>
        <p class="page-subtitle">请购单号来自公司系统，可在提交前自行修改</p>
      </div>
    </div>
    <n-card title="请购信息"
      ><n-form label-placement="top"
        ><n-form-item label="请购单号" required
          ><n-input
            v-model:value="model.request_no"
            maxlength="128"
            placeholder="例如：申购单-2026年7月17日" /></n-form-item
        ><n-form-item label="申购人（从申购计划带入）"
          ><n-input
            :value="applicantName"
            disabled
            placeholder="选择申购物资后自动带入" /></n-form-item
        ><n-form-item label="备注"
          ><n-input
            v-model:value="model.remark"
            type="textarea"
            maxlength="1000"
            show-count
            placeholder="例如：7 月检修备件" /></n-form-item></n-form></n-card
    ><n-card title="请购明细">
      <div class="request-lines">
        <div class="request-head">
          <span>申购物资</span><span>申请数量</span><span>用途</span><span>项目子项</span
          ><span>操作</span>
        </div>
        <div
          v-for="(line, i) in model.lines"
          :key="i"
          class="request-line"
          :class="{ uncoded: line.material && !line.material.material_code }"
        >
          <div>
            <PurchaseMaterialSelector
              v-model:value="line.purchase_material_id"
              @select="selectMaterial(i, $event)"
            />
            <div
              v-if="line.material && !line.material.material_code"
              class="danger-text line-warning"
            >
              无物料编码，不能提交
              <n-button text type="error" @click="goCompleteCode(line)">去补充编码</n-button>
            </div>
          </div>
          <QuantityInput v-model:value="line.requested_qty" :decimal-places="1"
            ><template #suffix>{{ line.material?.unit_name }}</template></QuantityInput
          ><n-input
            v-model:value="line.usage"
            maxlength="500"
            placeholder="必填用途"
          /><ProjectSubitemSelector v-model:value="line.project_subitem_id" /><n-button
            text
            type="error"
            :disabled="model.lines.length === 1"
            @click="remove(i)"
            >删除</n-button
          >
        </div>
        <n-button dashed block @click="add">+ 添加明细</n-button>
      </div>
      <n-alert v-if="uncodedLines.length" type="warning" style="margin-top: 16px"
        >第
        {{ uncodedLines.map((x) => x.index).join('、') }} 行没有物料编码，只能保存草稿。</n-alert
      ><n-alert v-if="responsibleIds.length > 1" type="error" style="margin-top: 16px"
        >所选计划的申购负责人不一致，请拆分为不同请购单。</n-alert
      > </n-card
    ><n-space justify="end"
      ><n-button @click="router.back()">取消</n-button
      ><n-button :loading="saving" @click="saveDraft">保存草稿</n-button
      ><n-button
        type="primary"
        :loading="saving"
        :disabled="uncodedLines.length > 0"
        @click="saveAndSubmit"
        >保存并提交</n-button
      ></n-space
    >
  </div>
</template>

<style scoped>
.request-lines {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.request-head,
.request-line {
  display: grid;
  grid-template-columns: minmax(260px, 1.4fr) 150px minmax(200px, 1fr) minmax(250px, 1.2fr) 50px;
  gap: 10px;
  align-items: start;
}
.request-head {
  color: #6b7280;
  font-size: 13px;
  padding: 0 4px;
}
.request-line {
  padding: 8px;
  border: 1px solid transparent;
  border-radius: 6px;
}
.request-line.uncoded {
  border-color: #f2c97d;
  background: #fffaf0;
}
.line-warning {
  font-size: 12px;
  margin-top: 4px;
}
</style>
