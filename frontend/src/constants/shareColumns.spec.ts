import { describe, expect, it } from 'vitest'
import {
  defaultShareColumnKeys,
  SHARE_PLAN_COLUMNS,
  SHARE_RECORD_COLUMNS,
  shareColumnOptions,
} from './shareColumns'

// 与后端 SharePlanColumn / ShareRecordColumn Literal 保持一致，防止前后端键漂移。
const PLAN_KEYS = [
  'plan_date',
  'material_code',
  'category',
  'urgency',
  'demand_department',
  'name',
  'model_spec',
  'planned_qty',
  'actual_demand_person',
  'purchase_responsible',
  'subitem_no',
  'usage',
  'status',
  'images',
]

const RECORD_KEYS = [
  'plan_date',
  'purchase_order_no',
  'trace_no',
  'category',
  'demand_department',
  'material_name',
  'model_spec',
  'purchase_qty',
  'actual_demand_person',
  'purchase_responsible',
  'salesperson',
  'subitem_no',
  'usage',
  'status',
  'images',
]

describe('shareColumns', () => {
  it('申购计划列键与后端 Literal 一致且无重复、label 非空', () => {
    const keys = SHARE_PLAN_COLUMNS.map((option) => option.key)
    expect(keys).toEqual(PLAN_KEYS)
    expect(new Set(keys).size).toBe(keys.length)
    for (const option of SHARE_PLAN_COLUMNS) expect(option.label.length).toBeGreaterThan(0)
  })

  it('申购记录列键与后端 Literal 一致且无重复、label 非空', () => {
    const keys = SHARE_RECORD_COLUMNS.map((option) => option.key)
    expect(keys).toEqual(RECORD_KEYS)
    expect(new Set(keys).size).toBe(keys.length)
    for (const option of SHARE_RECORD_COLUMNS) expect(option.label.length).toBeGreaterThan(0)
  })

  it('shareColumnOptions 按类型返回对应列定义', () => {
    expect(shareColumnOptions('purchase_plan')).toBe(SHARE_PLAN_COLUMNS)
    expect(shareColumnOptions('purchase_record')).toBe(SHARE_RECORD_COLUMNS)
  })

  it('默认展示列 = 全部列去掉「状态」', () => {
    expect(defaultShareColumnKeys('purchase_plan')).toEqual(
      PLAN_KEYS.filter((key) => key !== 'status'),
    )
    expect(defaultShareColumnKeys('purchase_record')).toEqual(
      RECORD_KEYS.filter((key) => key !== 'status'),
    )
    expect(defaultShareColumnKeys('purchase_plan')).not.toContain('status')
    expect(defaultShareColumnKeys('purchase_record')).not.toContain('status')
  })
})
