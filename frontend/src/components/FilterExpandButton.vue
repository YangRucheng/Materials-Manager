<script setup lang="ts">
import { NButton } from 'naive-ui'

/**
 * 移动端筛选折叠开关。
 * - 桌面端（>768px）默认隐藏：折叠/展开由全局 CSS 断点控制，桌面始终全量展示筛选。
 * - 移动端（≤768px）显示：点击在「更多筛选 / 收起筛选」间切换。
 */
defineProps<{ expanded: boolean }>()
const emit = defineEmits<{ 'update:expanded': [value: boolean] }>()
</script>

<template>
  <NButton
    size="small"
    quaternary
    class="filter-collapse-btn"
    :aria-expanded="expanded"
    @click="emit('update:expanded', !expanded)"
  >
    <template #icon>
      <svg
        class="filter-collapse-chevron"
        :class="{ 'is-expanded': expanded }"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </template>
    {{ expanded ? '收起筛选' : '更多筛选' }}
  </NButton>
</template>

<style scoped>
.filter-collapse-chevron {
  transition: transform 0.2s ease;
}
.filter-collapse-chevron.is-expanded {
  transform: rotate(180deg);
}
</style>
