import { describe, expect, it } from 'vitest'
import { defaultPurchaseOrderNo } from './purchase'

describe('默认申购单号', () => {
  it('按上海时区生成日期编号', () => {
    expect(defaultPurchaseOrderNo(new Date('2026-07-16T16:30:05Z'))).toBe('申购 2026/7/17')
  })
})
