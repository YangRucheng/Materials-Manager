import { apiBaseUrl, joinUrl } from '@/config/env'

export function downloadBlob(content: Blob, filename: string): void {
  const url = URL.createObjectURL(content)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

/** 导出文件匿名下载链接（后端该端点不鉴权，凭 uuid7 直接拉取）。 */
export function exportDownloadUrl(fileUuid: string): string {
  return joinUrl(apiBaseUrl, `excel-export-jobs/files/${encodeURIComponent(fileUuid)}`)
}

/** 以浏览器原生下载方式从 URL 保存文件（无 Authorization 头，不依赖 blob 拉取）。
 * 同源时 `download` 属性指定文件名；跨源时由服务端 Content-Disposition 决定。 */
export function downloadFromUrl(url: string, filename?: string): void {
  const anchor = document.createElement('a')
  anchor.href = url
  if (filename) anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

/** 从 Content-Disposition 头解析文件名（服务端生成的下载名，优先于前端拼接）。 */
export function filenameFromContentDisposition(value: string | null | undefined): string | null {
  if (!value) return null
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(value)
  if (utf8?.[1]) {
    try {
      return decodeURIComponent(utf8[1])
    } catch {
      return utf8[1]
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(value)
  return plain?.[1] ? plain[1] : null
}

/** 下载 Blob 并优先采用服务端 Content-Disposition 提供的文件名，缺失时回退。 */
export function downloadBlobWithDisposition(
  content: Blob,
  disposition: string | null | undefined,
  fallbackFilename: string,
): void {
  downloadBlob(content, filenameFromContentDisposition(disposition) ?? fallbackFilename)
}
