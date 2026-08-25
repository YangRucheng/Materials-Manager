import { describe, expect, it } from 'vitest'
import { inventoryModeOptionsFor } from './settings'

describe('inventoryModeOptionsFor（二级库库存功能选项）', () => {
  it('完整模式提供 禁用/仅查询/可读写', () => {
    expect(inventoryModeOptionsFor('full')).toEqual(['disabled', 'query_only', 'read_write'])
  })

  it('精简模式只提供 禁用/仅查询，不含可读写', () => {
    const options = inventoryModeOptionsFor('lite')
    expect(options).toEqual(['disabled', 'query_only'])
    expect(options).not.toContain('read_write')
  })
})
