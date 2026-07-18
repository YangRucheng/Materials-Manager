<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import type { PurchaseRequest, StockMaterial, StockMaterialWrite } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { inventoryApi } from '@/api/inventory'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionaries'
import StatusSteps from '@/components/StatusSteps.vue'
import MaterialSelector from '@/components/MaterialSelector.vue'
import { requestStatusLabels, statusTagType } from '@/utils/status'
import { formatShanghaiTime } from '@/utils/time'
import { subtractDecimal, compareDecimal } from '@/utils/decimal'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const dict = useDictionaryStore()
const message = useMessage()
const request = ref<PurchaseRequest | null>(null)
const loading = ref(true)
const actionModal = reactive({ show: false, action: '', title: '', reason: '' })
const linkModal = reactive({
  show: false,
  lineId: 0,
  purchaseMaterialId: 0,
  mode: 'link' as 'link' | 'create',
  stockId: null as number | null,
  quantity: '',
  requestNo: '',
  name: '',
  model_spec: '',
  unit_id: null as number | null,
  remark: '',
})
const stockPreview = ref<StockMaterial | undefined>()
const saving = ref(false)
const canPurchase = computed(() => auth.can('purchase:write'))
const canWarehouse = computed(() => auth.can('warehouse:write'))
const handler = computed(
  () => auth.user?.role === 'PURCHASE_ADMIN' || auth.user?.role === 'SUPER_ADMIN',
)
async function load() {
  loading.value = true
  try {
    request.value = await procurementApi.request(Number(route.params.id))
  } finally {
    loading.value = false
  }
}
async function act(action: string, payload: Record<string, unknown> = {}) {
  if (!request.value) return
  try {
    request.value = await procurementApi.requestAction(request.value.id, action, payload)
    message.success('操作成功')
    actionModal.show = false
  } catch (e) {
    message.error(e instanceof Error ? e.message : '操作失败')
  }
}
function openReason(action: string, title: string) {
  Object.assign(actionModal, { show: true, action, title, reason: '' })
}
function submitReason() {
  if (!actionModal.reason.trim()) {
    message.error('必须填写原因')
    return
  }
  void act(actionModal.action, { reason: actionModal.reason })
}
async function inbound(line: PurchaseRequest['lines'][number]) {
  try {
    const prepared = await procurementApi.prepareInbound(line.id)
    if (prepared.stock_material_id) {
      await router.push({
        name: 'inbound',
        query: {
          material_id: prepared.stock_material_id,
          quantity: prepared.remaining_qty,
          purchase_line_id: line.id,
          request_no: prepared.purchase_request_no,
        },
      })
      return
    }
    Object.assign(linkModal, {
      show: true,
      lineId: line.id,
      purchaseMaterialId: prepared.purchase_material_id,
      mode: 'link',
      stockId: null,
      quantity: prepared.remaining_qty,
      requestNo: prepared.purchase_request_no,
      name: prepared.material_name,
      model_spec: prepared.model_spec,
      unit_id: null,
      remark: '请购首次到货创建',
    })
    stockPreview.value = undefined
  } catch (e) {
    message.error(e instanceof Error ? e.message : '准备入库失败')
  }
}
async function continueInbound() {
  saving.value = true
  try {
    let stockId = linkModal.stockId
    if (linkModal.mode === 'create') {
      if (!linkModal.name.trim() || !linkModal.model_spec.trim() || !linkModal.unit_id) {
        message.error('请完整填写新物资信息')
        return
      }
      const payload: StockMaterialWrite = {
        name: linkModal.name,
        model_spec: linkModal.model_spec,
        unit_id: linkModal.unit_id,
        remark: linkModal.remark,
        image_ids: [],
      }
      const stock = await inventoryApi.createMaterial(payload)
      stockId = stock.id
    }
    if (!stockId) {
      message.error('请选择二级库物资')
      return
    }
    await procurementApi.linkStock(linkModal.purchaseMaterialId, stockId)
    linkModal.show = false
    await router.push({
      name: 'inbound',
      query: {
        material_id: stockId,
        quantity: linkModal.quantity,
        purchase_line_id: linkModal.lineId,
        request_no: linkModal.requestNo,
      },
    })
  } catch (e) {
    message.error(e instanceof Error ? e.message : '关联失败')
  } finally {
    saving.value = false
  }
}
onMounted(() => {
  void dict.load()
  void load()
})
</script>

<template>
  <div v-if="request" v-loading="loading" class="page">
    <div class="page-header">
      <div>
        <n-button text @click="router.back()">← 返回请购单</n-button>
        <h1 class="page-title">{{ request.request_no }}</h1>
        <p class="page-subtitle">
          <n-tag :type="statusTagType(request.status)">{{
            requestStatusLabels[request.status]
          }}</n-tag>
        </p>
      </div>
      <n-space>
        <n-button
          v-if="canPurchase && ['DRAFT', 'RETURNED'].includes(request.status)"
          @click="router.push({ name: 'purchase-request-new', query: { edit: request.id } })"
          >编辑</n-button
        ><n-button
          v-if="canPurchase && ['DRAFT', 'RETURNED'].includes(request.status)"
          type="primary"
          @click="act('submit')"
          >提交</n-button
        ><n-button
          v-if="canPurchase && ['DRAFT', 'RETURNED'].includes(request.status)"
          @click="act('cancel')"
          >取消</n-button
        ><n-button
          v-if="handler && request.status === 'SUBMITTED'"
          type="primary"
          @click="act('accept')"
          >受理</n-button
        ><n-button
          v-if="handler && ['SUBMITTED', 'PROCESSING'].includes(request.status)"
          @click="openReason('return', '退回请购')"
          >退回</n-button
        ><n-button
          v-if="handler && ['PROCESSING', 'PARTIALLY_RECEIVED'].includes(request.status)"
          type="error"
          @click="openReason('close', '关闭请购')"
          >关闭</n-button
        >
      </n-space>
    </div>
    <n-card><StatusSteps :status="request.status" type="request" /></n-card
    ><n-card title="请购信息"
      ><n-descriptions bordered :column="3"
        ><n-descriptions-item label="申购人">{{ request.applicant_name }}</n-descriptions-item
        ><n-descriptions-item label="受理人">{{ request.handler_name || '—' }}</n-descriptions-item
        ><n-descriptions-item label="提交时间">{{
          formatShanghaiTime(request.submitted_at)
        }}</n-descriptions-item
        ><n-descriptions-item label="请购单号">{{ request.request_no }}</n-descriptions-item
        ><n-descriptions-item label="备注" :span="2">{{
          request.remark || '—'
        }}</n-descriptions-item
        ><n-descriptions-item v-if="request.return_reason" label="退回原因" :span="3"
          ><span class="danger-text">{{ request.return_reason }}</span></n-descriptions-item
        ><n-descriptions-item v-if="request.close_reason" label="关闭原因" :span="3">{{
          request.close_reason
        }}</n-descriptions-item></n-descriptions
      ></n-card
    >
    <n-card title="请购明细"
      ><n-table :single-line="false"
        ><thead>
          <tr>
            <th>物料</th>
            <th>规格</th>
            <th>申请 / 已到 / 未到</th>
            <th>用途</th>
            <th>项目子项</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="line in request.lines" :key="line.id">
            <td>
              {{ line.material_code_snapshot || '无编码' }}<br /><strong>{{
                line.material_name_snapshot
              }}</strong>
            </td>
            <td>{{ line.model_spec_snapshot }}</td>
            <td>
              {{ line.requested_qty }} / <span class="success-text">{{ line.received_qty }}</span> /
              {{ subtractDecimal(line.requested_qty, line.received_qty) }}
              {{ line.unit_name_snapshot }}
            </td>
            <td>{{ line.usage }}</td>
            <td>
              {{ line.project_code_snapshot }} / {{ line.subitem_no_snapshot }}
              {{ line.subitem_name_snapshot }}
            </td>
            <td>
              <n-button
                v-if="
                  canWarehouse &&
                  ['PROCESSING', 'PARTIALLY_RECEIVED'].includes(request.status) &&
                  compareDecimal(line.received_qty, line.requested_qty) < 0
                "
                size="small"
                type="primary"
                @click="inbound(line)"
                >到货入库</n-button
              >
            </td>
          </tr>
        </tbody></n-table
      ></n-card
    >
    <div class="detail-grid">
      <n-card title="关联入库记录"
        ><n-button
          text
          type="primary"
          @click="
            router.push({ name: 'operations', query: { purchase_request_no: request.request_no } })
          "
          >查看该请购的全部入库流水 →</n-button
        ></n-card
      ><n-card title="状态日志"
        ><n-timeline
          ><n-timeline-item
            v-for="event in request.events"
            :key="event.id"
            :title="event.action"
            :content="`${event.operator_name}${event.remark ? '：' + event.remark : ''}`"
            :time="formatShanghaiTime(event.occurred_at)" /></n-timeline
      ></n-card>
    </div>
    <n-modal
      v-model:show="actionModal.show"
      preset="card"
      :title="actionModal.title"
      style="width: 520px"
      ><n-form-item label="原因" required
        ><n-input
          v-model:value="actionModal.reason"
          type="textarea"
          maxlength="500"
          show-count /></n-form-item
      ><template #footer
        ><n-space justify="end"
          ><n-button @click="actionModal.show = false">取消</n-button
          ><n-button type="primary" @click="submitReason">确认</n-button></n-space
        ></template
      ></n-modal
    >
    <n-modal
      v-model:show="linkModal.show"
      preset="card"
      title="首次到货：建立二级库物资关联"
      style="width: 680px"
      :mask-closable="false"
      ><n-tabs v-model:value="linkModal.mode" type="segment"
        ><n-tab-pane name="link" tab="关联已有物资"
          ><MaterialSelector
            v-model:value="linkModal.stockId"
            @select="stockPreview = $event"
          /><n-alert v-if="stockPreview" type="info" style="margin-top: 12px"
            >将关联：{{ stockPreview.name }} / {{ stockPreview.model_spec }} /
            {{ stockPreview.unit_name }}</n-alert
          ></n-tab-pane
        ><n-tab-pane name="create" tab="新建二级库物资"
          ><n-form label-placement="top"
            ><div class="form-grid">
              <n-form-item label="名称" required
                ><n-input v-model:value="linkModal.name" /></n-form-item
              ><n-form-item label="型号规格" required
                ><n-input v-model:value="linkModal.model_spec" /></n-form-item
              ><n-form-item label="计量单位" required
                ><n-select v-model:value="linkModal.unit_id" :options="dict.unitOptions"
              /></n-form-item>
            </div>
            <n-form-item label="备注"
              ><n-input
                v-model:value="linkModal.remark" /></n-form-item></n-form></n-tab-pane></n-tabs
      ><template #footer
        ><n-space justify="end"
          ><n-button @click="linkModal.show = false">取消</n-button
          ><n-button type="primary" :loading="saving" @click="continueInbound"
            >建立关联并继续入库</n-button
          ></n-space
        ></template
      ></n-modal
    >
  </div>
</template>
