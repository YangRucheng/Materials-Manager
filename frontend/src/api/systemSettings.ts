import { apiClient } from './client'
import type {
  ImageAccelerationSettings,
  MiniProgramFeatures,
  WebhookChannelSettings,
  WebhookChannelSettingsWrite,
  WebhookPlatform,
  WebhookTestInput,
  WebhookTestResult,
} from './generated'

export const systemSettingsApi = {
  imageAcceleration: () =>
    apiClient
      .get<ImageAccelerationSettings>('/system-settings/image-acceleration', { timeout: 3000 })
      .then((response) => response.data),
  miniProgramFeatures: () =>
    apiClient
      .get<MiniProgramFeatures>('/system-settings/mini-program-features', { timeout: 3000 })
      .then((response) => response.data),
  webhooks: () =>
    apiClient
      .get<WebhookChannelSettings[]>('/system-settings/webhooks')
      .then((response) => response.data),
  updateWebhook: (platform: WebhookPlatform, data: WebhookChannelSettingsWrite) =>
    apiClient
      .put<WebhookChannelSettings>(`/system-settings/webhooks/${platform}`, data)
      .then((response) => response.data),
  testWebhook: (platform: WebhookPlatform, data: WebhookTestInput) =>
    apiClient
      .post<WebhookTestResult>(`/system-settings/webhooks/${platform}/test`, data)
      .then((response) => response.data),
}
