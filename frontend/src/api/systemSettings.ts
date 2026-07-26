import { apiClient } from './client'
import type { MiniProgramCodeSettings } from './generated'

export const systemSettingsApi = {
  miniProgramCode: () =>
    apiClient
      .get<MiniProgramCodeSettings>('/system-settings/mini-program-code')
      .then((response) => response.data),
}
