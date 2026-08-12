import { apiClient } from './client'
import type { VersionInfo } from './generated'

export const versionApi = {
  get: () => apiClient.get<VersionInfo>('/version').then((response) => response.data),
}
