import { apiClient } from './client'
import type {
  AiSearchExpandResult,
  AiSearchSettings,
  AiSearchSettingsWrite,
  AiSearchStatus,
  AiSearchTestResult,
} from './generated'

export const aiSearchApi = {
  expand: (value: string) =>
    apiClient
      .post<AiSearchExpandResult>('/ai-search/expand', { value })
      .then((response) => response.data),
  status: () =>
    apiClient.get<AiSearchStatus>('/ai-search/status').then((response) => response.data),
  settings: () =>
    apiClient.get<AiSearchSettings>('/ai-search/settings').then((response) => response.data),
  updateSettings: (payload: AiSearchSettingsWrite) =>
    apiClient
      .put<AiSearchSettings>('/ai-search/settings', payload)
      .then((response) => response.data),
  testSettings: () =>
    apiClient
      .post<AiSearchTestResult>('/ai-search/settings/test', undefined, { timeout: 35_000 })
      .then((response) => response.data),
}
