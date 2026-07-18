<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { PurchaseMaterial } from '@/api/generated'
import { procurementApi } from '@/api/procurement'

defineProps<{ value: number | null; disabled?: boolean }>()
const emit = defineEmits<{
  'update:value': [value: number | null]
  select: [material?: PurchaseMaterial]
}>()
const materials = ref<PurchaseMaterial[]>([])
const loading = ref(false)
const options = computed(() =>
  materials.value
    .filter((x) => x.enabled)
    .map((x) => ({
      label: `${x.material_code || '无编码'}｜${x.name}｜${x.model_spec}`,
      value: x.id,
      style: x.material_code ? undefined : { color: '#d03050' },
    })),
)
async function load() {
  loading.value = true
  try {
    materials.value = (await procurementApi.materials({ page_size: 200, enabled: true })).items
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
    clearable
    placeholder="选择申购物资"
    @update:value="update"
  />
</template>
