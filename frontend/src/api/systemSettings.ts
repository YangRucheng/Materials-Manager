import { apiClient } from './client'
import type { ImageAccelerationSettings } from './generated'

export const systemSettingsApi = {
  imageAcceleration: () =>
    apiClient
      .get<ImageAccelerationSettings>('/system-settings/image-acceleration', { timeout: 3000 })
      .then((response) => response.data),
}
