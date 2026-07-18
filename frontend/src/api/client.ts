import axios, { AxiosError } from 'axios'
import type { ApiError } from './generated'

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
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15_000,
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['X-Request-ID'] = crypto.randomUUID()
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('auth_user')
      if (location.pathname !== '/login') location.assign('/login')
    }
    const payload = error.response?.data
    return Promise.reject(
      payload?.code
        ? new AppError(payload)
        : new AppError({ code: 'NETWORK_ERROR', message: '网络连接失败，请稍后重试' }),
    )
  },
)
