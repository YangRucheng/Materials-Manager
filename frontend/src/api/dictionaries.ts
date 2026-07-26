import { apiClient } from './client'
import type { MeasurementUnit, MiniProgramUser, Page, User } from './generated'

export const dictionaryApi = {
  units: (params?: Record<string, unknown>) =>
    apiClient.get<Page<MeasurementUnit>>('/measurement-units', { params }).then((r) => r.data),
  users: (params?: Record<string, unknown>) =>
    apiClient.get<Page<User>>('/users', { params }).then((r) => r.data),
  createUnit: (payload: Partial<MeasurementUnit>) =>
    apiClient.post<MeasurementUnit>('/measurement-units', payload).then((r) => r.data),
  updateUnit: (id: number, payload: Partial<MeasurementUnit>) =>
    apiClient.patch<MeasurementUnit>(`/measurement-units/${id}`, payload).then((r) => r.data),
  createUser: (payload: Partial<User> & { password?: string }) =>
    apiClient.post<User>('/users', payload).then((r) => r.data),
  updateUser: (id: number, payload: Partial<User> & { password?: string }) =>
    apiClient.patch<User>(`/users/${id}`, payload).then((r) => r.data),
  deleteUser: (id: number) => apiClient.delete(`/users/${id}`),
  miniProgramUsers: (params?: Record<string, unknown>) =>
    apiClient.get<Page<MiniProgramUser>>('/mini-program-users', { params }).then((r) => r.data),
  updateMiniProgramUser: (id: number, payload: Partial<MiniProgramUser>) =>
    apiClient.patch<MiniProgramUser>(`/mini-program-users/${id}`, payload).then((r) => r.data),
  deleteMiniProgramUser: (id: number, version: number) =>
    apiClient.delete(`/mini-program-users/${id}`, { params: { version } }),
}
