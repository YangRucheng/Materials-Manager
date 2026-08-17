export function downloadBlob(content: Blob, filename: string): void {
  const url = URL.createObjectURL(content)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
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
