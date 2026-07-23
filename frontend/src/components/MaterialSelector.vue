<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { StockMaterial } from '@/api/generated'
import { inventoryApi } from '@/api/inventory'

const props = defineProps<{ value: number | null; disabled?: boolean; excludeIds?: number[] }>()
const emit = defineEmits<{
  'update:value': [value: number | null]
  select: [material?: StockMaterial]
}>()
const materials = ref<StockMaterial[]>([])
const loading = ref(false)
const options = computed(() =>
  materials.value
    .filter((x) => !props.excludeIds?.includes(x.id))
    .map((x) => ({
      label: `${x.name}｜${x.model_spec}`,
      value: x.id,
    })),
)
async function load(keyword = '') {
  loading.value = true
  try {
    materials.value = (
      await inventoryApi.materials({ page_size: 200, keyword: keyword || undefined })
    ).items
  } finally {
    loading.value = false
  }
}
function update(value: number | null) {
  emit('update:value', value)
  emit(
    'select',
    materials.value.find((x) => x.id === value),
  )
}
onMounted(load)
</script>

<template>
  <n-select
    :value="value"
    :options="options"
    :loading="loading"
    :disabled="disabled"
    filterable
    remote
    clearable
    placeholder="选择二级库物资"
    @search="load"
    @update:value="update"
  />
</template>
