import { apiClient } from './client'
import type { ManagedUser, MiniProgramUser, MiniProgramUserMergeInput, Page } from './generated'

export const dictionaryApi = {
  users: (params?: Record<string, unknown>) =>
    apiClient.get<Page<ManagedUser>>('/users', { params }).then((r) => r.data),
  createUser: (payload: Partial<ManagedUser> & { password?: string }) =>
    apiClient.post<ManagedUser>('/users', payload).then((r) => r.data),
  updateUser: (id: number, payload: Partial<ManagedUser> & { password?: string }) =>
    apiClient.patch<ManagedUser>(`/users/${id}`, payload).then((r) => r.data),
  regenerateUserApiToken: (id: number, version: number) =>
    apiClient
      .post<ManagedUser>(`/users/${id}/api-token/regenerate`, { version })
      .then((r) => r.data),
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
