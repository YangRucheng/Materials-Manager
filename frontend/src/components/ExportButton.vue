<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NDropdown } from 'naive-ui'
import type { ExportOption } from '@/types/export'

const props = withDefaults(
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

const directOption = computed(() => (props.options.length === 1 ? props.options[0] : null))

function selectOption(key: string | number) {
  emit('select', String(key))
}

function selectDirectOption() {
  const option = directOption.value
  if (!option || option.disabled || props.disabled || props.loading) return
  emit('select', option.key)
}
</script>

<template>
  <NButton
    v-if="directOption"
    class="export-button"
    :loading="loading"
    :disabled="disabled || loading || directOption.disabled"
    :title="directOption.label"
    @click="selectDirectOption"
  >
    导出
  </NButton>
  <NDropdown
    v-else
    trigger="click"
    placement="bottom-end"
    :options="options"
    @select="selectOption"
  >
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
