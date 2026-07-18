import { describe, expect, it } from 'vitest'
import { defaultPurchaseRequestNo, findUncodedLineNumbers } from './purchase'

describe('请购提交前编码校验', () => {
  it('返回所有无编码明细的 1 基行号', () => {
    const lines = [
      {
        purchase_material_id: 1,
        requested_qty: '1',
        usage: '检修',
        project_subitem_id: 1,
        material: { material_code: 'DQ-1' },
      },
      {
        purchase_material_id: 2,
        requested_qty: '2',
        usage: '备用',
        project_subitem_id: 1,
        material: {},
      },
      {
        purchase_material_id: 3,
        requested_qty: '3',
        usage: '更换',
        project_subitem_id: 1,
        material: {},
      },
    ]
    expect(findUncodedLineNumbers(lines)).toEqual([2, 3])
  })
})

describe('申购记录默认编号', () => {
  it('按上海时区生成年月日名称', () => {
    expect(defaultPurchaseRequestNo(new Date('2026-07-16T16:30:00Z'))).toBe(
      '申购记录-2026年7月17日',
    )
  })
})
