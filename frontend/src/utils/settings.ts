import type { MiniProgramFeatureMode, SecondaryWarehouseMode } from '@/api/generated'

/**
 * 小程序端「二级库库存」功能开关的可用选项。
 * 精简模式下二级库仅可查看（不支持出入库），因此不提供「可读写」。
 */
export function inventoryModeOptionsFor(mode: SecondaryWarehouseMode): MiniProgramFeatureMode[] {
  if (mode === 'lite') {
    return ['disabled', 'query_only']
  }
  return ['disabled', 'query_only', 'read_write']
}
