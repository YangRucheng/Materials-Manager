import { describe, expect, it } from 'vitest'
import { maxImageBytes, validateImageSelection } from './image'

describe('图片上传限制', () => {
  it('只接受 JPG、PNG 和 WebP', () => {
    expect(
      validateImageSelection(0, [new File(['x'], 'part.gif', { type: 'image/gif' })]),
    ).toContain('不是支持的图片类型')
  })
  it('限制单图 10 MB', () => {
    const file = new File([new Uint8Array(maxImageBytes + 1)], 'large.png', { type: 'image/png' })
    expect(validateImageSelection(0, [file])).toContain('超过 10 MB')
  })
  it('每个物资最多九张', () => {
    const file = new File(['x'], 'ok.webp', { type: 'image/webp' })
    expect(validateImageSelection(9, [file])).toContain('最多上传 9 张')
  })
})
