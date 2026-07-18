import { describe, expect, it } from 'vitest'
import { defaultPurchaseOrderNo, findUncodedLineNumbers } from './purchase'

describe('请购提交前编码校验', () => {
  it('返回所有无编码明细的 1 基行号', () => {
    const lines = [
      {
        purchase_material_id: 1,
        requested_qty: '1',
        usage: '检修',
        subitem_no: '01-01',
        material: { material_code: 'DQ-1' },
      },
      {
        purchase_material_id: 2,
        requested_qty: '2',
        usage: '备用',
        subitem_no: '01-01',
        material: {},
      },
      {
        purchase_material_id: 3,
        requested_qty: '3',
        usage: '更换',
        subitem_no: '01-01',
        material: {},
      },
    ]
    expect(findUncodedLineNumbers(lines)).toEqual([2, 3])
  })
})

describe('默认申购单号', () => {
  it('按上海时区生成日期编号', () => {
    expect(defaultPurchaseOrderNo(new Date('2026-07-16T16:30:05Z'))).toBe('申购 2026/7/17')
  })
})
