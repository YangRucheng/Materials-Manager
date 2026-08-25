import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSettingsStore } from './settings'
import { systemSettingsApi } from '@/api/systemSettings'

vi.mock('@/api/systemSettings', () => ({
  systemSettingsApi: {
    miniProgramFeatures: vi.fn(),
  },
}))

const fullFeatures = {
  inventory_mode: 'read_write',
  huaxing_inventory_mode: 'query_only',
  purchase_plans_mode: 'query_only',
  purchase_records_mode: 'query_only',
  material_codes_mode: 'query_only',
  secondary_warehouse_mode: 'full',
} as const

describe('settings store（二级库模式）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(systemSettingsApi.miniProgramFeatures).mockReset()
  })

  it('未加载时默认完整模式', () => {
    const store = useSettingsStore()
    expect(store.secondaryWarehouseMode).toBe('full')
    expect(store.isLiteMode).toBe(false)
  })

  it('load 后按返回模式更新 isLiteMode（精简模式）', async () => {
    vi.mocked(systemSettingsApi.miniProgramFeatures).mockResolvedValue({
      ...fullFeatures,
      secondary_warehouse_mode: 'lite',
    })
    const store = useSettingsStore()
    await store.load()
    expect(store.secondaryWarehouseMode).toBe('lite')
    expect(store.isLiteMode).toBe(true)
    expect(store.loaded).toBe(true)
  })

  it('load 后为完整模式时 isLiteMode 为 false', async () => {
    vi.mocked(systemSettingsApi.miniProgramFeatures).mockResolvedValue(fullFeatures)
    const store = useSettingsStore()
    await store.load()
    expect(store.secondaryWarehouseMode).toBe('full')
    expect(store.isLiteMode).toBe(false)
  })

  it('拉取失败回退完整模式', async () => {
    vi.mocked(systemSettingsApi.miniProgramFeatures).mockRejectedValue(new Error('network'))
    const store = useSettingsStore()
    await store.load()
    expect(store.secondaryWarehouseMode).toBe('full')
    expect(store.isLiteMode).toBe(false)
  })

  it('只拉取一次', async () => {
    vi.mocked(systemSettingsApi.miniProgramFeatures).mockResolvedValue(fullFeatures)
    const store = useSettingsStore()
    await store.load()
    await store.load()
    expect(systemSettingsApi.miniProgramFeatures).toHaveBeenCalledTimes(1)
  })
})
