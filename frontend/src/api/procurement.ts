import { apiClient } from './client'
import type {
  Page,
  MovePurchasePlansWrite,
  PreparedInbound,
  PurchaseMaterial,
  PurchaseMaterialWrite,
  PurchaseRecord,
  PurchaseRequest,
  PurchaseRequestWrite,
  StockOperation,
} from './generated'

export const procurementApi = {
  materials: (params?: Record<string, unknown>) =>
    apiClient.get<Page<PurchaseMaterial>>('/purchase-materials', { params }).then((r) => r.data),
  material: (id: number) =>
    apiClient.get<PurchaseMaterial>(`/purchase-materials/${id}`).then((r) => r.data),
  createMaterial: (payload: PurchaseMaterialWrite) =>
    apiClient.post<PurchaseMaterial>('/purchase-materials', payload).then((r) => r.data),
  updateMaterial: (id: number, payload: PurchaseMaterialWrite) =>
    apiClient.patch<PurchaseMaterial>(`/purchase-materials/${id}`, payload).then((r) => r.data),
  deleteMaterial: (id: number, version: number) =>
    apiClient.delete(`/purchase-materials/${id}`, { params: { version } }),
  linkStock: (id: number, stock_material_id: number) =>
    apiClient
      .post<PurchaseMaterial>(`/purchase-materials/${id}/link-stock-material`, {
        stock_material_id,
      })
      .then((r) => r.data),
  movePlanToRecord: (id: number, payload: MovePurchasePlansWrite) =>
    apiClient
      .post<PurchaseRecord>(`/purchase-materials/${id}/move-to-record`, payload)
      .then((r) => r.data),
  batchMovePlansToRecord: (materialIds: number[], payload: MovePurchasePlansWrite) =>
    apiClient
      .post<PurchaseRecord[]>('/purchase-materials/batch-move-to-record', {
        ...payload,
        material_ids: materialIds,
      })
      .then((r) => r.data),
  uncodedMaterials: (params?: Record<string, unknown>) =>
    apiClient
      .get<Page<PurchaseMaterial>>('/purchase-materials', { params: { ...params, coded: false } })
      .then((r) => r.data),
  requests: (params?: Record<string, unknown>) =>
    apiClient.get<Page<PurchaseRequest>>('/purchase-requests', { params }).then((r) => r.data),
  request: (id: number) =>
    apiClient.get<PurchaseRequest>(`/purchase-requests/${id}`).then((r) => r.data),
  createRequest: (payload: PurchaseRequestWrite) =>
    apiClient.post<PurchaseRequest>('/purchase-requests', payload).then((r) => r.data),
  updateRequest: (id: number, payload: PurchaseRequestWrite) =>
    apiClient.patch<PurchaseRequest>(`/purchase-requests/${id}`, payload).then((r) => r.data),
  requestAction: (id: number, action: string, payload: Record<string, unknown> = {}) =>
    apiClient
      .post<PurchaseRequest>(`/purchase-requests/${id}/${action}`, payload)
      .then((r) => r.data),
  receipts: (id: number) =>
    apiClient.get<StockOperation[]>(`/purchase-requests/${id}/receipts`).then((r) => r.data),
  prepareInbound: (lineId: number) =>
    apiClient
      .post<PreparedInbound>(`/purchase-request-lines/${lineId}/prepare-inbound`)
      .then((r) => r.data),
  records: (params?: Record<string, unknown>) =>
    apiClient.get<Page<PurchaseRecord>>('/purchase-records', { params }).then((r) => r.data),
  record: (lineId: number) =>
    apiClient.get<PurchaseRecord>(`/purchase-records/${lineId}`).then((r) => r.data),
  updateRecord: (lineId: number, payload: MovePurchasePlansWrite & { version: number }) =>
    apiClient.patch<PurchaseRecord>(`/purchase-records/${lineId}`, payload).then((r) => r.data),
}
