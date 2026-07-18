<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string; type: 'code' | 'request' }>()
const codeSteps = [
  { key: 'DRAFT', title: '草稿' },
  { key: 'SUBMITTED', title: '已提交' },
  { key: 'PROCESSING', title: '处理中' },
  { key: 'COMPLETED', title: '已完成' },
]
const requestSteps = [
  { key: 'DRAFT', title: '草稿' },
  { key: 'SUBMITTED', title: '已提交' },
  { key: 'PROCESSING', title: '处理中' },
  { key: 'PARTIALLY_RECEIVED', title: '部分到货' },
  { key: 'COMPLETED', title: '已完成' },
]
const steps = computed(() => (props.type === 'code' ? codeSteps : requestSteps))
const current = computed(() => {
  if (['RETURNED'].includes(props.status)) return 1
  if (['REJECTED', 'CANCELED', 'CLOSED'].includes(props.status))
    return Math.max(
      0,
      steps.value.findIndex((x) => x.key === 'PROCESSING'),
    )
  const index = steps.value.findIndex((x) => x.key === props.status)
  return Math.max(0, index)
})
const statusType = computed(() =>
  ['REJECTED', 'CANCELED', 'CLOSED'].includes(props.status)
    ? 'error'
    : ['RETURNED'].includes(props.status)
      ? 'wait'
      : 'process',
)
</script>

<template>
  <n-steps :current="current + 1" :status="statusType">
    <n-step v-for="step in steps" :key="step.key" :title="step.title" />
  </n-steps>
</template>
