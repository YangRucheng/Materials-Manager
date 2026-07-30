import { apiClient } from './client'
import type { LoginRequest, LoginResponse, TokenPairResponse, User } from './generated'

export const authApi = {
  login: (payload: LoginRequest) =>
    apiClient.post<LoginResponse>('/auth/login', payload).then((r) => r.data),
  refresh: (refreshToken: string) =>
    apiClient
      .post<TokenPairResponse>('/auth/refresh', { refresh_token: refreshToken })
      .then((r) => r.data),
  me: () => apiClient.get<User>('/auth/me').then((r) => r.data),
}
