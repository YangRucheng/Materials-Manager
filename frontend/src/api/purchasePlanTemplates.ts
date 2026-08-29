import { apiClient } from './client'
import type {
  Page,
  PagedQueryParams,
  PurchaseMaterial,
  PurchasePlanTemplate,
  PurchasePlanTemplateFilterOptions,
  PurchasePlanTemplateUpdate,
  PurchasePlanTemplateWrite,
} from './generated'

/** 周期性计划（申购计划模板）列表查询 */
export interface PurchasePlanTemplateListQuery extends PagedQueryParams {
  name?: string
  model_spec?: string
  actual_demand_person?: string
  purchase_responsible?: string
  category?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export const purchasePlanTemplateApi = {
  templates: (params?: PurchasePlanTemplateListQuery) =>
    apiClient
      .get<Page<PurchasePlanTemplate>>('/purchase-plan-templates', { params })
      .then((r) => r.data),
  templateFilterOptions: () =>
    apiClient
      .get<PurchasePlanTemplateFilterOptions>('/purchase-plan-templates/filter-options')
      .then((r) => r.data),
  template: (id: number) =>
    apiClient.get<PurchasePlanTemplate>(`/purchase-plan-templates/${id}`).then((r) => r.data),
  createTemplate: (payload: PurchasePlanTemplateWrite) =>
    apiClient.post<PurchasePlanTemplate>('/purchase-plan-templates', payload).then((r) => r.data),
  updateTemplate: (id: number, payload: PurchasePlanTemplateUpdate) =>
    apiClient
      .patch<PurchasePlanTemplate>(`/purchase-plan-templates/${id}`, payload)
      .then((r) => r.data),
  deleteTemplate: (id: number, version: number) =>
    apiClient.delete(`/purchase-plan-templates/${id}`, {
      headers: { 'If-Match': String(version) },
    }),
  /** 把模板完整复制为一条今天的申购计划（plan_date=生成当天），模板本身不删除 */
  generatePurchasePlan: (id: number) =>
    apiClient.post<PurchaseMaterial>(`/purchase-plan-templates/${id}/generate`).then((r) => r.data),
}
