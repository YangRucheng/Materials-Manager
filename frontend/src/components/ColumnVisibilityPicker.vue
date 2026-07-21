<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { NButton, NCheckbox, NPopover } from 'naive-ui'

interface ColumnOption {
  label: string
  value: string
}

const props = defineProps<{
  value: string[]
  options: ColumnOption[]
  storageKey?: string
}>()

const emit = defineEmits<{
  'update:value': [value: string[]]
}>()

function updateColumn(value: string, checked: boolean) {
  if (!checked && props.value.length === 1) return
  const next = checked
    ? [...props.value, value]
    : props.value.filter((current) => current !== value)
  emit('update:value', next)
}

function restoreColumns() {
  if (!props.storageKey) return
  try {
    const stored = JSON.parse(localStorage.getItem(props.storageKey) || 'null')
    if (!Array.isArray(stored)) return
    const storedKeys = new Set(stored.filter((value): value is string => typeof value === 'string'))
    const restored = props.options
      .map((option) => option.value)
      .filter((value) => storedKeys.has(value))
    if (restored.length) emit('update:value', restored)
  } catch {
    return
  }
}

function persistColumns(value: string[]) {
  if (!props.storageKey || !value.length) return
  try {
    localStorage.setItem(props.storageKey, JSON.stringify(value))
  } catch {
    return
  }
}

onMounted(restoreColumns)
watch(() => props.value, persistColumns, { deep: true })
</script>

<template>
  <NPopover trigger="click" placement="bottom-end" :width="320">
    <template #trigger>
      <NButton secondary class="column-picker-trigger">已显示 {{ value.length }} 个字段</NButton>
    </template>
    <div class="column-picker-header">
      <strong>选择展示字段</strong>
      <span>至少保留 1 个</span>
    </div>
    <div class="column-picker-grid">
      <NCheckbox
        v-for="option in options"
        :key="option.value"
        :checked="value.includes(option.value)"
        :disabled="value.length === 1 && value[0] === option.value"
        @update:checked="updateColumn(option.value, $event)"
      >
        {{ option.label }}
      </NCheckbox>
    </div>
  </NPopover>
</template>

<style scoped>
.column-picker-trigger {
  min-width: 148px;
}

.column-picker-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 14px;
}

.column-picker-header span {
  color: #8a919f;
  font-size: 12px;
}

.column-picker-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 20px;
}
</style>
