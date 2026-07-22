import { describe, expect, it } from 'vitest'
import { compactRouteQuery, routeQueryPositiveInteger, routeQueryString } from './routeQuery'

describe('route query helpers', () => {
  it('reads scalar and array query values', () => {
    expect(routeQueryString('接触器')).toBe('接触器')
    expect(routeQueryString(['第一个', '第二个'])).toBe('第一个')
    expect(routeQueryString(undefined)).toBe('')
  })

  it('only accepts positive integer pagination values', () => {
    expect(routeQueryPositiveInteger('3', 1)).toBe(3)
    expect(routeQueryPositiveInteger('0', 1)).toBe(1)
    expect(routeQueryPositiveInteger('invalid', 20)).toBe(20)
  })

  it('removes empty query values and trims strings', () => {
    expect(
      compactRouteQuery({
        page: 2,
        name: ' 接触器 ',
        model_spec: '',
        status: null,
      }),
    ).toEqual({ page: '2', name: '接触器' })
  })
})
