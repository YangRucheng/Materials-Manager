<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { inventoryApi } from '@/api/inventory'
import type { DashboardSummary, InventoryBalance } from '@/api/generated'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const summary = ref<DashboardSummary>({
  stock_material_count: 0,
  low_stock_count: 0,
  uncoded_purchase_material_count: 0,
  purchase_record_count: 0,
})
const lowStock = ref<InventoryBalance[]>([])
const cards = computed(() => [
  {
    label: '库存物资',
    value: summary.value.stock_material_count,
    hint: '二级库物资项数',
    color: '#2080f0',
  },
  {
    label: '低库存',
    value: summary.value.low_stock_count,
    hint: '按最低库存阈值统计',
    color: '#d03050',
  },
  {
    label: '未编码物资',
    value: summary.value.uncoded_purchase_material_count,
    hint: '可直接进入申购计划编辑',
    color: '#f0a020',
  },
  {
    label: '申购记录',
    value: summary.value.purchase_record_count,
    hint: '用于整理和统计',
    color: '#18a058',
  },
])
async function load() {
  loading.value = true
  try {
    const [sum, low] = await Promise.all([
      inventoryApi.summary(),
      inventoryApi.lowStock({ page_size: 5 }),
    ])
    summary.value = sum
    lowStock.value = low.items
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">工作台</h1>
        <p class="page-subtitle">库存与申购业务概览</p>
      </div>
      <n-button @click="load">刷新数据</n-button>
    </div>
    <div class="stat-grid">
      <n-card v-for="card in cards" :key="card.label"
        ><div class="stat">
          <span class="stat-label">{{ card.label }}</span
          ><strong :style="{ color: card.color }">{{ card.value }}</strong
          ><span class="muted">{{ card.hint }}</span>
        </div></n-card
      >
    </div>
    <n-card
      ><template #header><span class="card-title">快捷入口</span></template>
      <n-space>
        <n-button
          v-if="auth.can('warehouse:write')"
          type="primary"
          @click="router.push('/warehouse/inbound')"
          >办理入库</n-button
        >
        <n-button v-if="auth.can('warehouse:write')" @click="router.push('/warehouse/outbound')"
          >办理出库</n-button
        >
        <n-button v-if="auth.can('purchase:write')" @click="router.push('/procurement/materials')"
          >新物资申购</n-button
        >
        <n-button @click="router.push('/warehouse/stock?low_stock=true')">低库存补库</n-button>
      </n-space>
    </n-card>
    <n-card
      ><template #header
        ><div class="page-header">
          <span class="card-title">低库存提醒</span
          ><n-button text type="primary" @click="router.push('/warehouse/stock?low_stock=true')"
            >查看全部</n-button
          >
        </div></template
      >
      <n-table :bordered="false" :single-line="false"
        ><thead>
          <tr>
            <th>物资</th>
            <th>当前库存</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in lowStock" :key="item.stock_material_id">
            <td>
              {{ item.name }}<br /><span class="muted">{{ item.model_spec }}</span>
            </td>
            <td>{{ item.current_qty }} {{ item.unit_name }}</td>
            <td>
              <n-tag type="error">低库存</n-tag>
            </td>
            <td>
              <n-button
                text
                type="primary"
                @click="router.push(`/warehouse/materials/${item.stock_material_id}`)"
                >查看详情</n-button
              >
            </td>
          </tr>
          <tr v-if="!lowStock.length">
            <td colspan="4"><n-empty description="当前没有低库存物资" /></td>
          </tr></tbody
      ></n-table>
    </n-card>
  </div>
</template>

<style scoped>
.stat {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stat-label {
  color: #4b5563;
}
.stat strong {
  font-size: 30px;
  line-height: 1.2;
}
</style>
