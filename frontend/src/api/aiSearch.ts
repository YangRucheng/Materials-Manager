import { apiClient } from './client'
import type {
  AiSearchSettings,
  AiSearchSettingsWrite,
  AiSearchStatus,
  AiSearchTestResult,
} from './generated'

export const aiSearchApi = {
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
      .post<AiSearchTestResult>('/ai-search/settings/test')
      .then((response) => response.data),
}
