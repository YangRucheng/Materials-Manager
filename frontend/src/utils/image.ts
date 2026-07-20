export const allowedImageTypes = ['image/jpeg', 'image/png', 'image/webp'] as const
export const maxImageBytes = 10 * 1024 * 1024

export function imageUrl(fileId: string): string {
  return `/api/v1/files/images/${encodeURIComponent(fileId)}`
}

export function imagePreviewUrl(fileId: string, size: number): string {
  return `${imageUrl(fileId)}?size=${size}`
}

export function validateImageSelection(
  existingCount: number,
  files: File[],
  maxCount = 9,
): string | null {
  if (existingCount + files.length > maxCount) return `每个物资最多上传 ${maxCount} 张图片`
  const invalidType = files.find(
    (file) => !allowedImageTypes.includes(file.type as (typeof allowedImageTypes)[number]),
  )
  if (invalidType) return `${invalidType.name} 不是支持的图片类型`
  const oversized = files.find((file) => file.size > maxImageBytes)
  if (oversized) return `${oversized.name} 超过 10 MB`
  return null
}
