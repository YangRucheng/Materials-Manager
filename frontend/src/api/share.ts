import { apiClient } from './client'
import type { ShareCreateRequest, SharePublicView, ShareRead } from './generated'

/** 链接分享：把勾选的申购计划/申购记录分享为无鉴权页面。 */
export const shareApi = {
  /** 创建匿名分享链接（需登录），返回 token 与失效时间。 */
  createShare: (payload: ShareCreateRequest) =>
    apiClient.post<ShareRead>('/shares', payload).then((r) => r.data),
  /** 匿名读取分享数据（无需登录，凭 token）。 */
  getShare: (token: string) =>
    apiClient.get<SharePublicView>(`/shares/${encodeURIComponent(token)}`).then((r) => r.data),
  /** 撤回分享（仅创建者本人或超级管理员）。 */
  revokeShare: (token: string) =>
    apiClient.delete(`/shares/${encodeURIComponent(token)}`).then((r) => r.data),
}
