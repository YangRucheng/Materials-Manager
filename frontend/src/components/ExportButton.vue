<script setup lang="ts">
import { NButton, NDropdown } from 'naive-ui'
import type { ExportOption } from '@/types/export'

withDefaults(
  defineProps<{
    options: ExportOption[]
    loading?: boolean
    disabled?: boolean
  }>(),
  {
    loading: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  select: [key: string]
}>()

function selectOption(key: string | number) {
  emit('select', String(key))
}
</script>

<template>
  <NDropdown trigger="click" placement="bottom-end" :options="options" @select="selectOption">
    <NButton
      class="export-button"
      :loading="loading"
      :disabled="disabled || loading || !options.length"
      aria-label="打开导出菜单"
      title="选择导出方式"
    >
      <span>导出</span>
      <span class="export-button__chevron" aria-hidden="true" />
    </NButton>
  </NDropdown>
</template>

<style scoped>
.export-button {
  min-width: 88px;
}

.export-button__chevron {
  width: 6px;
  height: 6px;
  margin: -3px 0 0 8px;
  border-right: 1.5px solid currentcolor;
  border-bottom: 1.5px solid currentcolor;
  transform: rotate(45deg);
}
</style>
