<script setup lang="ts">
import { computed } from 'vue'
import { compareDecimal, isDecimalString } from '@/utils/decimal'

const props = withDefaults(
  defineProps<{
    value: string
    decimalPlaces?: number
    max?: string
    disabled?: boolean
    placeholder?: string
  }>(),
  { decimalPlaces: 1, max: undefined, placeholder: '请输入数量' },
)
const emit = defineEmits<{ 'update:value': [value: string] }>()

const status = computed(() => {
  if (!props.value) return undefined
  if (!isDecimalString(props.value, props.decimalPlaces)) return 'error'
  if (props.max && compareDecimal(props.value, props.max) > 0) return 'error'
  return 'success'
})

function update(value: string) {
  if (/^\d*(?:\.\d{0,1})?$/.test(value)) emit('update:value', value)
}
</script>

<template>
  <n-input
    :value="value"
    :disabled="disabled"
    :placeholder="placeholder"
    :status="status"
    inputmode="decimal"
    @update:value="update"
  >
    <template v-if="$slots.suffix" #suffix><slot name="suffix" /></template>
  </n-input>
</template>
