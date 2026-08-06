import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { apiBaseUrl } from '@/config/env'
import type { ApiError, TokenPairResponse } from './generated'

type RetryableRequestConfig = InternalAxiosRequestConfig & { _authRetry?: boolean }

let refreshRequest: Promise<string> | null = null

function clearSession() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('auth_user')
}

async function renewAccessToken(): Promise<string> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) throw new Error('missing refresh token')
  const response = await axios.post<TokenPairResponse>(
    `${apiBaseUrl}/auth/refresh`,
    { refresh_token: refreshToken },
    { timeout: 15_000, headers: { 'X-Request-ID': crypto.randomUUID() } },
  )
  localStorage.setItem('access_token', response.data.access_token)
  localStorage.setItem('refresh_token', response.data.refresh_token)
  return response.data.access_token
}

export class AppError extends Error {
  code: string
  details?: Record<string, unknown>
  requestId?: string

  constructor(error: ApiError) {
    super(error.message)
    this.name = 'AppError'
    this.code = error.code
    this.details = error.details
    this.requestId = error.request_id
  }
}

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: 15_000,
  paramsSerializer: { indexes: null },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['X-Request-ID'] = crypto.randomUUID()
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as RetryableRequestConfig | undefined
    if (
      error.response?.status === 401 &&
      error.response.data?.code === 'INVALID_TOKEN' &&
      originalRequest &&
      !originalRequest._authRetry &&
      localStorage.getItem('refresh_token')
    ) {
      originalRequest._authRetry = true
      refreshRequest ??= renewAccessToken().finally(() => {
        refreshRequest = null
      })
      try {
        const accessToken = await refreshRequest
        originalRequest.headers.Authorization = `Bearer ${accessToken}`
        return apiClient(originalRequest)
      } catch {
        clearSession()
        if (location.pathname !== '/login') location.assign('/login')
      }
    } else if (error.response?.status === 401) {
      clearSession()
      if (location.pathname !== '/login') location.assign('/login')
    }
    const payload = error.response?.data
    const fallback: ApiError = error.response
      ? {
          code: 'SERVER_ERROR',
          message: `服务请求失败（HTTP ${error.response.status}），请稍后重试`,
          request_id: originalRequest?.headers?.['X-Request-ID'] ?? '',
        }
      : { code: 'NETWORK_ERROR', message: '无法连接服务器，请检查网络后重试', request_id: '' }
    return Promise.reject(payload?.code ? new AppError(payload) : new AppError(fallback))
  },
)
