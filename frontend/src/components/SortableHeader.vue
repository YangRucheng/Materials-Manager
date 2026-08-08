<script lang="ts">
// 普通 script 块导出类型（script setup 不能导出命名类型）
export type SortOptionKey = 'default' | 'asc' | 'desc'
</script>

<script setup lang="ts">
import { computed } from 'vue'
import { NDropdown } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'

const props = defineProps<{
  label: string
  sortByKey: string
  sortBy: string | null
  sortOrder: 'asc' | 'desc' | null
}>()

const emit = defineEmits<{ select: [value: SortOptionKey] }>()

const sortOptions: DropdownOption[] = [
  { label: '默认', key: 'default' },
  { label: '升序', key: 'asc' },
  { label: '降序', key: 'desc' },
]
const isActive = computed(() => props.sortBy === props.sortByKey && props.sortOrder !== null)
// 菜单打开时高亮当前项：本列未排序显示「默认」，否则显示升/降
const currentValue = computed<SortOptionKey>(() =>
  props.sortBy === props.sortByKey && props.sortOrder ? props.sortOrder : 'default',
)

function handleSelect(key: string | number) {
  emit('select', key as SortOptionKey)
}
</script>

<template>
  <NDropdown
    trigger="click"
    placement="bottom-start"
    :options="sortOptions"
    :value="currentValue"
    @select="handleSelect"
  >
    <span class="sortable-header" :class="{ 'sortable-header--active': isActive }">
      <span class="sortable-header__label">{{ label }}</span>
      <span v-if="isActive" class="sortable-header__arrow" aria-hidden="true">{{
        sortOrder === 'asc' ? '↑' : '↓'
      }}</span>
      <span v-else class="sortable-header__chevron" aria-hidden="true" />
    </span>
  </NDropdown>
</template>

<style scoped>
.sortable-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
}

.sortable-header--active {
  color: var(--color-primary);
}

.sortable-header__arrow {
  font-size: 12px;
}

.sortable-header__chevron {
  width: 6px;
  height: 6px;
  margin-top: -3px;
  border-right: 1.5px solid currentcolor;
  border-bottom: 1.5px solid currentcolor;
  transform: rotate(45deg);
  opacity: 0.6;
}
</style>
