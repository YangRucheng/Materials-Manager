import { describe, expect, it } from 'vitest'
import {
  joinUrl,
  normalizeBaseUrl,
  resolveApiBaseUrl,
  resolveImageBaseUrl,
  resolveMcpUrl,
} from './env'

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

  it('后端服务器地址自动补全 API 路径', () => {
    expect(resolveApiBaseUrl('https://api.example.com')).toBe('https://api.example.com/api/v1')
    expect(resolveApiBaseUrl('https://api.example.com/api/v1')).toBe(
      'https://api.example.com/api/v1',
    )
  })

  it('图床服务器地址自动补全图片接口路径', () => {
    expect(resolveImageBaseUrl('https://img.example.com', '/api/v1')).toBe(
      'https://img.example.com/api/v1/files/images',
    )
    expect(resolveImageBaseUrl(undefined, 'https://api.example.com/api/v1')).toBe(
      'https://api.example.com/api/v1/files/images',
    )
  })

  it('生成带令牌的绝对 MCP 地址', () => {
    expect(resolveMcpUrl('/api/v1', 'token-value', 'https://app.example.com')).toBe(
      'https://app.example.com/api/v1/mcp/?token=token-value',
    )
    expect(
      resolveMcpUrl('https://api.example.com/api/v1', 'a+b/c', 'https://app.example.com'),
    ).toBe('https://api.example.com/api/v1/mcp/?token=a%2Bb%2Fc')
  })
})
