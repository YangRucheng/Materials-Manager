import { apiClient } from './client'
import type {
  ImageAccelerationSettings,
  WebhookChannelSettings,
  WebhookChannelSettingsWrite,
  WebhookPlatform,
  WebhookTestResult,
} from './generated'

export const systemSettingsApi = {
  imageAcceleration: () =>
    apiClient
      .get<ImageAccelerationSettings>('/system-settings/image-acceleration', { timeout: 3000 })
      .then((response) => response.data),
  webhooks: () =>
    apiClient
      .get<WebhookChannelSettings[]>('/system-settings/webhooks')
      .then((response) => response.data),
  updateWebhook: (platform: WebhookPlatform, data: WebhookChannelSettingsWrite) =>
    apiClient
      .put<WebhookChannelSettings>(`/system-settings/webhooks/${platform}`, data)
      .then((response) => response.data),
  testWebhook: (platform: WebhookPlatform) =>
    apiClient
      .post<WebhookTestResult>(`/system-settings/webhooks/${platform}/test`)
      .then((response) => response.data),
}
