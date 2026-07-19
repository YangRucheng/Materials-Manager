import { describe, expect, it } from 'vitest'
import { imagePreviewUrl, maxImageBytes, validateImageSelection } from './image'

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
  it('为服务端图片添加预览尺寸且保留原有参数', () => {
    expect(imagePreviewUrl('/api/v1/files/images/id', 192)).toBe('/api/v1/files/images/id?size=192')
    expect(imagePreviewUrl('/image?id=1', 320)).toBe('/image?id=1&size=320')
    expect(imagePreviewUrl('data:image/png;base64,abc', 192)).toBe('data:image/png;base64,abc')
  })
})
