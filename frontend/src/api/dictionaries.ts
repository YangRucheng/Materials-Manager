import { apiClient } from './client'
import type { MiniProgramUser, MiniProgramUserMergeInput, Page, User } from './generated'

export const dictionaryApi = {
  users: (params?: Record<string, unknown>) =>
    apiClient.get<Page<User>>('/users', { params }).then((r) => r.data),
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
  mergeMiniProgramUsers: (targetId: number, payload: MiniProgramUserMergeInput) =>
    apiClient
      .post<MiniProgramUser>(`/mini-program-users/${targetId}/merge`, payload)
      .then((r) => r.data),
}
