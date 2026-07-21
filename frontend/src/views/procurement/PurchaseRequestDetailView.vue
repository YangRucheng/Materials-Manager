<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import type { PurchaseRecord, StockMaterial, StockMaterialWrite } from '@/api/generated'
import { procurementApi } from '@/api/procurement'
import { inventoryApi } from '@/api/inventory'
import { useAuthStore } from '@/stores/auth'
import { useDictionaryStore } from '@/stores/dictionaries'
import MaterialSelector from '@/components/MaterialSelector.vue'
import { requestStatusLabels, statusTagType } from '@/utils/status'
import { dateToTimestamp, formatDate, toShanghaiDate } from '@/utils/time'
import { imagePreviewUrl, imageUrl } from '@/utils/image'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const dictionaries = useDictionaryStore()
const message = useMessage()
const record = ref<PurchaseRecord | null>(null)
const loading = ref(true)
const saving = ref(false)
const edit = reactive({
  purchase_order_no: '',
  trace_no: '',
  purchase_date: Date.now(),
  salesperson: '',
  remark: '',
})
const linkModal = reactive({
  show: false,
  mode: 'link' as 'link' | 'create',
  stockId: null as number | null,
  name: '',
  model_spec: '',
  unit_id: null as number | null,
  remark: '',
})
const stockPreview = ref<StockMaterial | undefined>()

async function load() {
  loading.value = true
  try {
    record.value = await procurementApi.record(Number(route.params.id))
    Object.assign(edit, {
      purchase_order_no: record.value.purchase_order_no || '',
      trace_no: record.value.trace_no || '',
      purchase_date: dateToTimestamp(record.value.purchase_date),
      salesperson: record.value.salesperson || '',
      remark: record.value.remark || '',
    })
  } finally {
    loading.value = false
  }
}

async function saveTracking() {
  if (!record.value || !edit.purchase_date) {
    message.error('请选择申购日期')
    return
  }
  saving.value = true
  try {
    record.value = await procurementApi.updateRecord(record.value.line_id, {
      purchase_order_no: edit.purchase_order_no.trim() || null,
      trace_no: edit.trace_no.trim() || null,
      purchase_date: toShanghaiDate(edit.purchase_date),
      salesperson: edit.salesperson || undefined,
      remark: edit.remark || undefined,
      version: record.value.version,
    })
    message.success('申购记录已保存')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function inbound() {
  if (!record.value) return
  try {
    const prepared = await procurementApi.prepareInbound(record.value.line_id)
    if (prepared.stock_material_id) {
      await router.push({
        name: 'inbound',
        query: {
          material_id: prepared.stock_material_id,
          quantity: prepared.remaining_qty,
          purchase_line_id: record.value.line_id,
          request_no: prepared.purchase_request_no || undefined,
        },
      })
      return
    }
    Object.assign(linkModal, {
      show: true,
      mode: 'link',
      stockId: null,
      name: prepared.material_name,
      model_spec: prepared.model_spec,
      unit_id: null,
      remark: '申购物资首次到货创建',
    })
  } catch (error) {
    message.error(error instanceof Error ? error.message : '准备入库失败')
  }
}

async function continueInbound() {
  if (!record.value) return
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
      stockId = (await inventoryApi.createMaterial(payload)).id
    }
    if (!stockId) {
      message.error('请选择二级库物资')
      return
    }
    await procurementApi.linkStock(record.value.purchase_material_id, stockId)
    linkModal.show = false
    await router.push({
      name: 'inbound',
      query: {
        material_id: stockId,
        quantity: record.value.remaining_qty,
        purchase_line_id: record.value.line_id,
        request_no: record.value.trace_no || undefined,
      },
    })
  } catch (error) {
    message.error(error instanceof Error ? error.message : '关联失败')
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
  <div v-if="record" v-loading="loading" class="page">
    <div class="page-header">
      <div>
        <n-button text @click="router.back()">← 返回申购记录</n-button>
        <h1 class="page-title">{{ record.material_name }}</h1>
        <p class="page-subtitle">
          {{ record.purchase_order_no || record.trace_no || '未填写单号' }} ·
          <n-tag :type="statusTagType(record.status)">{{
            requestStatusLabels[record.status]
          }}</n-tag>
        </p>
      </div>
      <n-space>
        <n-button
          v-if="auth.can('purchase:write')"
          type="primary"
          :loading="saving"
          @click="saveTracking"
          >保存</n-button
        >
        <n-button
          v-if="
            auth.can('warehouse:write') &&
            ['SUBMITTED', 'PROCESSING', 'PARTIALLY_RECEIVED'].includes(record.status) &&
            Number(record.remaining_qty) > 0
          "
          type="primary"
          @click="inbound"
          >到货入库</n-button
        >
      </n-space>
    </div>
    <n-card title="申购记录信息">
      <n-form label-placement="top" :disabled="!auth.can('purchase:write')">
        <div class="form-grid">
          <n-form-item label="申购单号">
            <n-input v-model:value="edit.purchase_order_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="追溯号">
            <n-input v-model:value="edit.trace_no" maxlength="128" placeholder="可留空" />
          </n-form-item>
          <n-form-item label="申购日期" required>
            <n-date-picker v-model:value="edit.purchase_date" type="date" class="full-width" />
          </n-form-item>
        </div>
        <n-form-item label="业务员"><n-input v-model:value="edit.salesperson" /></n-form-item>
        <n-form-item label="跟踪备注">
          <n-input v-model:value="edit.remark" type="textarea" maxlength="1000" show-count />
        </n-form-item>
      </n-form>
      <n-descriptions :column="3">
        <n-descriptions-item label="状态">{{
          requestStatusLabels[record.status]
        }}</n-descriptions-item>
        <n-descriptions-item label="计划数量"
          >{{ record.planned_qty }} {{ record.unit_name }}</n-descriptions-item
        >
        <n-descriptions-item label="已到数量"
          >{{ record.received_qty }} {{ record.unit_name }}</n-descriptions-item
        >
        <n-descriptions-item label="未到数量"
          >{{ record.remaining_qty }} {{ record.unit_name }}</n-descriptions-item
        >
        <n-descriptions-item label="申购负责人">{{
          record.purchase_responsible
        }}</n-descriptions-item>
        <n-descriptions-item label="实际需求人">{{
          record.actual_demand_person
        }}</n-descriptions-item>
      </n-descriptions>
    </n-card>
    <n-card title="物资与计划信息">
      <n-descriptions :column="3">
        <n-descriptions-item label="计划 ID">{{ record.plan_no }}</n-descriptions-item>
        <n-descriptions-item label="计划日期">{{
          formatDate(record.plan_date)
        }}</n-descriptions-item>
        <n-descriptions-item label="物料编码">{{ record.material_code }}</n-descriptions-item>
        <n-descriptions-item label="名称">{{ record.material_name }}</n-descriptions-item>
        <n-descriptions-item label="型号规格">{{ record.model_spec }}</n-descriptions-item>
        <n-descriptions-item label="用途">{{ record.usage }}</n-descriptions-item>
        <n-descriptions-item label="子项号" :span="2">{{
          record.subitem_no || '—'
        }}</n-descriptions-item>
      </n-descriptions>
      <n-divider>附件</n-divider>
      <n-space v-if="record.images.length">
        <n-image
          v-for="image in record.images"
          :key="image.id"
          :src="imagePreviewUrl(image.id, 320)"
          :preview-src="imageUrl(image.id)"
          width="120"
          height="120"
          object-fit="cover"
        />
      </n-space>
      <n-empty v-else description="暂无附件" size="small" />
    </n-card>
    <n-modal
      v-model:show="linkModal.show"
      preset="card"
      title="首次到货：建立二级库物资关联"
      style="width: 680px"
      :mask-closable="false"
    >
      <n-tabs v-model:value="linkModal.mode" type="segment">
        <n-tab-pane name="link" tab="关联已有物资">
          <MaterialSelector v-model:value="linkModal.stockId" @select="stockPreview = $event" />
          <n-alert v-if="stockPreview" type="info" style="margin-top: 12px">
            将关联：{{ stockPreview.name }} / {{ stockPreview.model_spec }} /
            {{ stockPreview.unit_name }}
          </n-alert>
        </n-tab-pane>
        <n-tab-pane name="create" tab="新建二级库物资">
          <n-form label-placement="top">
            <div class="form-grid">
              <n-form-item label="名称" required
                ><n-input v-model:value="linkModal.name"
              /></n-form-item>
              <n-form-item label="型号规格" required
                ><n-input v-model:value="linkModal.model_spec"
              /></n-form-item>
              <n-form-item label="计量单位" required>
                <n-select v-model:value="linkModal.unit_id" :options="dictionaries.unitOptions" />
              </n-form-item>
            </div>
            <n-form-item label="备注"><n-input v-model:value="linkModal.remark" /></n-form-item>
          </n-form>
        </n-tab-pane>
      </n-tabs>
      <template #footer>
        <n-space justify="end">
          <n-button @click="linkModal.show = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="continueInbound"
            >建立关联并继续入库</n-button
          >
        </n-space>
      </template>
    </n-modal>
  </div>
</template>
