import { describe, expect, it, vi } from 'vitest'
import {
  downloadBlobWithDisposition,
  downloadFromUrl,
  exportDownloadUrl,
  filenameFromContentDisposition,
} from './download'

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

describe('downloadFromUrl', () => {
  it('creates an anchor with the href and optional filename, then clicks and removes it', () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const appendChild = vi.spyOn(document.body, 'appendChild')
    const remove = vi.spyOn(HTMLAnchorElement.prototype, 'remove')

    downloadFromUrl(
      '/api/v1/excel-export-jobs/files/0195f1a2-0000-7000-8000-000000000001',
      '导出.xlsx',
    )

    expect(appendChild).toHaveBeenCalledTimes(1)
    const anchor = click.mock.instances[0] as unknown as HTMLAnchorElement
    expect(anchor.href).toContain('/excel-export-jobs/files/0195f1a2-0000-7000-8000-000000000001')
    expect(anchor.download).toBe('导出.xlsx')
    expect(click).toHaveBeenCalledTimes(1)
    expect(remove).toHaveBeenCalledTimes(1)
    click.mockRestore()
    appendChild.mockRestore()
    remove.mockRestore()
  })

  it('omits the download attribute when no filename is given', () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    downloadFromUrl('/api/v1/excel-export-jobs/files/0195f1a2-0000-7000-8000-000000000001')

    const anchor = click.mock.instances[0] as unknown as HTMLAnchorElement
    expect(anchor.download).toBe('')
    click.mockRestore()
  })
})

describe('exportDownloadUrl', () => {
  it('joins the api base url with the file uuid path', () => {
    expect(exportDownloadUrl('0195f1a2-0000-7000-8000-000000000001')).toBe(
      '/api/v1/excel-export-jobs/files/0195f1a2-0000-7000-8000-000000000001',
    )
  })
})
