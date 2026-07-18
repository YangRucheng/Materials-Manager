<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { User } from '@/api/generated'
import { dictionaryApi } from '@/api/dictionaries'

defineProps<{ value: number | null; disabled?: boolean }>()
const emit = defineEmits<{
  'update:value': [value: number | null]
  select: [user?: User]
}>()
const users = ref<User[]>([])
const loading = ref(false)
const options = computed(() =>
  users.value
    .filter((user) => user.enabled && user.role !== 'READ_ONLY')
    .map((user) => ({ label: user.display_name, value: user.id })),
)

async function load() {
  loading.value = true
  try {
    users.value = (await dictionaryApi.users({ page_size: 200 })).items
  } finally {
    loading.value = false
  }
}

function update(value: number | null) {
  emit('update:value', value)
  emit(
    'select',
    users.value.find((user) => user.id === value),
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
    placeholder="选择申购负责人"
    @update:value="update"
  />
</template>
