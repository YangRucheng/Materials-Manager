<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { inventoryApi } from '@/api/inventory'
import type { DashboardSummary, InventoryBalance } from '@/api/generated'

const router = useRouter()
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
    hint: '已建立档案的二级库物资',
    color: '#3f63d8',
  },
  {
    label: '低库存',
    value: summary.value.low_stock_count,
    hint: '当前库存已达到预警阈值',
    color: '#d94b64',
  },
  {
    label: '未编码物资',
    value: summary.value.uncoded_purchase_material_count,
    hint: '正常计划中待补录物料编码',
    color: '#d99020',
  },
  {
    label: '申购记录',
    value: summary.value.purchase_record_count,
    hint: '已转入申购记录的物资明细',
    color: '#229b6b',
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
    <n-card>
      <template #header>
        <div class="page-header">
          <div>
            <span class="card-title">低库存提醒</span>
            <div class="section-description">仅展示前 5 条，完整数据请前往库存查询</div>
          </div>
          <n-button text type="primary" @click="router.push('/warehouse/stock?low_stock=true')"
            >查看全部</n-button
          >
        </div>
      </template>
      <div class="table-scroll" style="--table-min-width: 680px">
        <n-table :bordered="false" :single-line="false"
          ><thead>
            <tr>
              <th>物资</th>
              <th>当前库存</th>
              <th>最低库存</th>
              <th>近6个月消耗</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in lowStock" :key="item.stock_material_id">
              <td>
                {{ item.name }}<br /><span class="muted">{{ item.model_spec }}</span>
              </td>
              <td>{{ item.current_qty }} {{ item.unit_name }}</td>
              <td>{{ item.minimum_qty ?? '—' }} {{ item.unit_name }}</td>
              <td>{{ item.suggested_purchase_qty }} {{ item.unit_name }}</td>
            </tr>
            <tr v-if="!lowStock.length">
              <td colspan="4"><n-empty description="当前没有低库存物资" /></td>
            </tr></tbody
        ></n-table>
      </div>
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
  color: var(--color-text);
  font-weight: 500;
}
.stat strong {
  font-size: 30px;
  font-weight: 650;
  line-height: 1.2;
}
.section-description {
  margin-top: 3px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 400;
}
</style>
