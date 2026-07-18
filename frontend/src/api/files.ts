import { apiClient } from './client'
import type { FileObject } from './generated'

export const fileApi = {
  uploadImage: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<FileObject>('/files/images', form).then((r) => r.data)
  },
  removeImage: (id: number) => apiClient.delete(`/files/images/${id}`),
}
