<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useDictionaryStore } from '@/stores/dictionaries'

defineProps<{ value: number | null; disabled?: boolean }>()
const emit = defineEmits<{ 'update:value': [value: number | null] }>()
const dictionaries = useDictionaryStore()
const options = computed(() =>
  dictionaries.projects
    .filter((x) => x.enabled)
    .map((x) => ({
      label: `${x.project_code} / ${x.subitem_no} ${x.subitem_name}`,
      value: x.id,
    })),
)
onMounted(() => void dictionaries.load())
</script>

<template>
  <n-select
    :value="value"
    :options="options"
    :disabled="disabled"
    filterable
    clearable
    placeholder="选择项目子项"
    @update:value="emit('update:value', $event)"
  />
</template>
