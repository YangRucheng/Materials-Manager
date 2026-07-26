import { apiClient } from './client'
import type { ImageAccelerationSettings, MiniProgramCodeSettings } from './generated'

export const systemSettingsApi = {
  miniProgramCode: () =>
    apiClient
      .get<MiniProgramCodeSettings>('/system-settings/mini-program-code')
      .then((response) => response.data),
  imageAcceleration: () =>
    apiClient
      .get<ImageAccelerationSettings>('/system-settings/image-acceleration', { timeout: 3000 })
      .then((response) => response.data),
}
