import { beforeEach, describe, expect, it } from 'vitest'
import {
  defaultPurchaseOrderNo,
  getLastPurchaseResponsible,
  rememberPurchaseResponsible,
} from './purchase'

describe('默认申购单号', () => {
  beforeEach(() => localStorage.clear())

  it('按上海时区生成日期编号', () => {
    expect(defaultPurchaseOrderNo(new Date('2026-07-16T16:30:05Z'))).toBe('申购 2026/7/17')
  })

  it('记住最后一次新增使用的申购负责人', () => {
    rememberPurchaseResponsible('  李工  ')

    expect(getLastPurchaseResponsible()).toBe('李工')
  })

  it('不使用空值覆盖已记住的负责人', () => {
    rememberPurchaseResponsible('王工')
    rememberPurchaseResponsible('   ')

    expect(getLastPurchaseResponsible()).toBe('王工')
  })
})
