import { describe, expect, it } from 'vitest'
import { joinUrl, normalizeBaseUrl } from './env'

describe('构建环境配置', () => {
  it('清理地址末尾斜杠', () => {
    expect(normalizeBaseUrl('https://api.example.com/api/v1/', '/api/v1')).toBe(
      'https://api.example.com/api/v1',
    )
    expect(normalizeBaseUrl(undefined, '/api/v1')).toBe('/api/v1')
  })

  it('稳定拼接绝对和相对地址', () => {
    expect(joinUrl('https://img.example.com/api/v1/files/images/', '/019abc')).toBe(
      'https://img.example.com/api/v1/files/images/019abc',
    )
    expect(joinUrl('/api/v1', 'files/images')).toBe('/api/v1/files/images')
  })
})
