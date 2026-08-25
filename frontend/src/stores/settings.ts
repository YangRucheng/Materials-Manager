import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { systemSettingsApi } from '@/api/systemSettings'
import type { SecondaryWarehouseMode } from '@/api/generated'

/**
 * 全局系统模式（公开配置端点在启动时拉取，供菜单/路由守卫在首次导航前同步读取）。
 * 二级库精简模式下：后台「二级库」tab 变为单一一级 tab（Excel 导入 + 只读查询）。
 */
export const useSettingsStore = defineStore('settings', () => {
  const secondaryWarehouseMode = ref<SecondaryWarehouseMode>('full')
  const isLiteMode = computed(() => secondaryWarehouseMode.value === 'lite')
  const loaded = ref(false)

  async function load() {
    if (loaded.value) return
    try {
      const features = await systemSettingsApi.miniProgramFeatures()
      secondaryWarehouseMode.value = features.secondary_warehouse_mode
    } catch {
      // 拉取失败回退完整模式，保证现有功能不受影响
      secondaryWarehouseMode.value = 'full'
    } finally {
      loaded.value = true
    }
  }

  return { secondaryWarehouseMode, isLiteMode, loaded, load }
})
