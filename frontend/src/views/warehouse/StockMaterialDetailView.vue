<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { inventoryApi } from '@/api/inventory'
import type { StockMaterial } from '@/api/generated'
import { useAuthStore } from '@/stores/auth'
import { formatShanghaiTime } from '@/utils/time'
import { compareDecimal, isDecimalString } from '@/utils/decimal'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const auth = useAuthStore()
const material = ref<StockMaterial | null>(null)
const loading = ref(true)
const saving = ref(false)
const policy = reactive({ minimum_qty: '0', target_qty: '0', enabled: true })
async function load() {
  loading.value = true
  try {
    material.value = await inventoryApi.material(Number(route.params.id))
    Object.assign(
      policy,
      material.value.replenishment_policy || { minimum_qty: '0', target_qty: '0', enabled: true },
    )
  } finally {
    loading.value = false
  }
}
async function savePolicy() {
  if (
    !isDecimalString(policy.minimum_qty, 1, true) ||
    !isDecimalString(policy.target_qty, 1, true) ||
    compareDecimal(policy.target_qty, policy.minimum_qty) < 0
  ) {
    message.error('目标库存必须大于或等于最低库存，且最多 3 位小数')
    return
  }
  saving.value = true
  try {
    material.value = await inventoryApi.savePolicy(Number(route.params.id), {
      ...policy,
      version: material.value?.version,
    })
    message.success('安全库存策略已保存')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<template>
  <div v-if="material" v-loading="loading" class="page">
    <div class="page-header">
      <div>
        <n-button text @click="router.back()">← 返回物资列表</n-button>
        <h1 class="page-title">{{ material.name }}</h1>
        <p class="page-subtitle">{{ material.model_spec }}</p>
      </div>
      <n-space v-if="auth.can('warehouse:write')"
        ><n-button @click="router.push({ name: 'inbound', query: { material_id: material.id } })"
          >入库</n-button
        ><n-button
          type="primary"
          @click="router.push({ name: 'outbound', query: { material_id: material.id } })"
          >出库</n-button
        ></n-space
      >
    </div>
    <div class="detail-grid">
      <n-card title="物资信息"
        ><n-descriptions label-placement="left" :column="2" bordered
          ><n-descriptions-item label="名称">{{ material.name }}</n-descriptions-item
          ><n-descriptions-item label="型号规格">{{ material.model_spec }}</n-descriptions-item
          ><n-descriptions-item label="计量单位">{{ material.unit_name }}</n-descriptions-item
          ><n-descriptions-item label="当前库存"
            ><strong>{{ material.current_qty }}</strong></n-descriptions-item
          ><n-descriptions-item label="状态"
            ><n-tag :type="material.enabled ? 'success' : 'default'">{{
              material.enabled ? '启用' : '停用'
            }}</n-tag></n-descriptions-item
          ><n-descriptions-item label="更新时间">{{
            formatShanghaiTime(material.updated_at)
          }}</n-descriptions-item
          ><n-descriptions-item label="备注" :span="2">{{
            material.remark || '—'
          }}</n-descriptions-item></n-descriptions
        ><n-divider>图片</n-divider
        ><n-space v-if="material.images.length"
          ><n-image
            v-for="image in material.images"
            :key="image.id"
            :src="image.url"
            width="120"
            height="120"
            object-fit="cover" /></n-space
        ><n-empty v-else description="暂无图片" size="small"
      /></n-card>
      <n-card title="安全库存策略"
        ><n-form label-placement="top"
          ><n-form-item label="最低库存"
            ><n-input v-model:value="policy.minimum_qty" :disabled="!auth.can('warehouse:write')"
              ><template #suffix>{{ material.unit_name }}</template></n-input
            ></n-form-item
          ><n-form-item label="目标库存"
            ><n-input v-model:value="policy.target_qty" :disabled="!auth.can('warehouse:write')"
              ><template #suffix>{{ material.unit_name }}</template></n-input
            ></n-form-item
          ><n-form-item
            ><n-switch
              v-model:value="policy.enabled"
              :disabled="!auth.can('warehouse:write')"
            />&nbsp;启用低库存预警</n-form-item
          ><n-button
            v-if="auth.can('warehouse:write')"
            type="primary"
            block
            :loading="saving"
            @click="savePolicy"
            >保存策略</n-button
          ></n-form
        ></n-card
      >
    </div>
  </div>
</template>
