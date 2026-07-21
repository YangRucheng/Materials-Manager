import { apiClient } from './client'
import type {
  Page,
  MovePurchasePlansWrite,
  PurchaseFilterOptions,
  PurchaseMaterial,
  PurchaseMaterialWrite,
  PurchaseRecord,
  PurchaseRecordWrite,
} from './generated'

export const procurementApi = {
  materials: (params?: Record<string, unknown>) =>
    apiClient.get<Page<PurchaseMaterial>>('/purchase-materials', { params }).then((r) => r.data),
  materialFilterOptions: (params?: Record<string, unknown>) =>
    apiClient
      .get<PurchaseFilterOptions>('/purchase-materials/filter-options', { params })
      .then((r) => r.data),
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
  exportPurchaseApplication: (materialIds: number[]) =>
    apiClient
      .post<Blob>(
        '/purchase-materials/export-purchase-application',
        { material_ids: materialIds },
        { responseType: 'blob' },
      )
      .then((r) => r.data),
  exportUncodedMaterials: (params?: Record<string, unknown>) =>
    apiClient
      .get<Blob>('/purchase-materials/export-uncoded', { params, responseType: 'blob' })
      .then((r) => r.data),
  uncodedMaterials: (params?: Record<string, unknown>) =>
    apiClient
      .get<Page<PurchaseMaterial>>('/purchase-materials', { params: { ...params, coded: false } })
      .then((r) => r.data),
  records: (params?: Record<string, unknown>) =>
    apiClient.get<Page<PurchaseRecord>>('/purchase-records', { params }).then((r) => r.data),
  recordFilterOptions: () =>
    apiClient.get<PurchaseFilterOptions>('/purchase-records/filter-options').then((r) => r.data),
  record: (lineId: number) =>
    apiClient.get<PurchaseRecord>(`/purchase-records/${lineId}`).then((r) => r.data),
  updateRecord: (lineId: number, payload: PurchaseRecordWrite) =>
    apiClient.patch<PurchaseRecord>(`/purchase-records/${lineId}`, payload).then((r) => r.data),
}
