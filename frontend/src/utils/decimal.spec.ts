import { describe, expect, it } from 'vitest'
import { compareDecimal, isDecimalString, normalizeDecimal, subtractDecimal } from './decimal'

describe('Decimal 字符串', () => {
  it('不经过 JavaScript 浮点数即可比较大数和三位小数', () => {
    expect(compareDecimal('999999999999999999.999', '999999999999999999.998')).toBe(1)
    expect(compareDecimal('0.10', '0.1')).toBe(0)
  })

  it('按单位小数位校验正数量', () => {
    expect(isDecimalString('12', 0)).toBe(true)
    expect(isDecimalString('12.1', 0)).toBe(false)
    expect(isDecimalString('0.125', 3)).toBe(true)
    expect(isDecimalString('0', 3)).toBe(false)
  })

  it('精确计算出库后库存', () => {
    expect(subtractDecimal('10.2', '0.1')).toBe('10.1')
    expect(subtractDecimal('2', '3.125')).toBe('-1.125')
    expect(normalizeDecimal('0002.500')).toBe('2.5')
  })
})
