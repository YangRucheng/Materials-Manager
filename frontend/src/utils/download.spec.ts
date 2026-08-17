import { describe, expect, it, vi } from 'vitest'
import { downloadBlobWithDisposition, filenameFromContentDisposition } from './download'

describe('filenameFromContentDisposition', () => {
  it('parses RFC 5987 UTF-8 filename*', () => {
    const value =
      "attachment; filename*=UTF-8''%E7%94%B3%E8%B4%AD%E8%AE%A1%E5%88%92%E5%AF%BC%E5%87%BA_20260817.xlsx"
    expect(filenameFromContentDisposition(value)).toBe('申购计划导出_20260817.xlsx')
  })

  it('parses plain quoted filename as fallback', () => {
    expect(filenameFromContentDisposition('attachment; filename="export.xlsx"')).toBe('export.xlsx')
  })

  it('returns null for missing or empty headers', () => {
    expect(filenameFromContentDisposition(null)).toBeNull()
    expect(filenameFromContentDisposition(undefined)).toBeNull()
    expect(filenameFromContentDisposition('')).toBeNull()
  })
})

describe('downloadBlobWithDisposition', () => {
  it('prefers server-provided filename over fallback', () => {
    // jsdom 不实现 URL.createObjectURL，直接注入桩。
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    const blob = new Blob(['x'], { type: 'application/octet-stream' })
    downloadBlobWithDisposition(blob, "attachment; filename*=UTF-8''a.xlsx", 'fallback.xlsx')

    expect(click).toHaveBeenCalledTimes(1)
    const anchor = click.mock.instances[0] as unknown as HTMLAnchorElement
    expect(anchor.download).toBe('a.xlsx')
    click.mockRestore()
  })

  it('falls back when disposition is absent', () => {
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const blob = new Blob(['x'], { type: 'application/octet-stream' })
    downloadBlobWithDisposition(blob, null, 'fallback.xlsx')

    const anchor = click.mock.instances[0] as unknown as HTMLAnchorElement
    expect(anchor.download).toBe('fallback.xlsx')
    click.mockRestore()
  })
})
