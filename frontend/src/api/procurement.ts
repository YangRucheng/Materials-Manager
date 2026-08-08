import { apiClient } from './client'
import type {
  MaterialCodeLibrary,
  MaterialCodeLibraryImportResult,
  Page,
  PagedQueryParams,
  MovePurchasePlansWrite,
  PurchaseFilterOptions,
  PurchaseMaterial,
  PurchaseMaterialBatchUpdate,
  PurchaseMaterialWrite,
  PurchasePlanStatus,
  PurchaseRecord,
  PurchaseRecordBatchUpdate,
  PurchaseRecordFilterOptions,
  PurchasePlanResultExportRequest,
  PurchaseRecordResultExportRequest,
  PurchaseRecordWrite,
} from './generated'

/** 申购计划列表查询（materials 与导出共享筛选字段） */
export interface PurchaseMaterialListQuery extends PagedQueryParams {
  moved?: boolean
  name?: string
  model_spec?: string
  actual_demand_person?: string
  empty_actual_demand_person?: boolean
  subitem_no?: string
  empty_subitem_no?: boolean
  category?: string
  status?: PurchasePlanStatus[]
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

/** 申购记录列表查询（records 与导出共享筛选字段） */
export interface PurchaseRecordListQuery extends PagedQueryParams {
  name?: string
  model_spec?: string
  trace_no?: string
  purchase_order_no?: string
  actual_demand_person?: string
  purchase_responsible?: string
  salesperson?: string
  status?: string
  empty_status?: boolean
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

/** 未编码物资查询（uncodedMaterials 内部追加 coded:false） */
export interface UncodedMaterialListQuery extends PagedQueryParams {
  status?: PurchasePlanStatus
}

/** 物料编码库列表查询 */
export interface MaterialCodeLibraryListQuery extends PagedQueryParams {
  material_code?: string
  name?: string
  model_spec?: string
}

/** 申购计划筛选下拉选项查询 */
export interface MaterialFilterOptionsQuery {
  moved?: boolean
}

export const procurementApi = {
  materialCodes: (params?: MaterialCodeLibraryListQuery) =>
    apiClient
      .get<Page<MaterialCodeLibrary>>('/material-code-library', { params })
      .then((r) => r.data),
  importMaterialCodes: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient
      .post<MaterialCodeLibraryImportResult>('/material-code-library/import', formData, {
        timeout: 120_000,
      })
      .then((r) => r.data)
  },
  materials: (params?: PurchaseMaterialListQuery) =>
    apiClient.get<Page<PurchaseMaterial>>('/purchase-materials', { params }).then((r) => r.data),
  materialFilterOptions: (params?: MaterialFilterOptionsQuery) =>
    apiClient
      .get<PurchaseFilterOptions>('/purchase-materials/filter-options', { params })
      .then((r) => r.data),
  material: (id: number) =>
    apiClient.get<PurchaseMaterial>(`/purchase-materials/${id}`).then((r) => r.data),
  createMaterial: (payload: PurchaseMaterialWrite) =>
    apiClient.post<PurchaseMaterial>('/purchase-materials', payload).then((r) => r.data),
  updateMaterial: (id: number, payload: PurchaseMaterialWrite) =>
    apiClient.patch<PurchaseMaterial>(`/purchase-materials/${id}`, payload).then((r) => r.data),
  batchUpdateMaterials: (payload: PurchaseMaterialBatchUpdate) =>
    apiClient.patch<PurchaseMaterial[]>('/purchase-materials/batch', payload).then((r) => r.data),
  deleteMaterial: (id: number, version: number) =>
    apiClient.delete(`/purchase-materials/${id}`, { headers: { 'If-Match': String(version) } }),
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
  exportMaterialResults: (payload: PurchasePlanResultExportRequest) =>
    apiClient
      .post<Blob>('/purchase-materials/export-results', payload, { responseType: 'blob' })
      .then((r) => r.data),
  exportUncodedMaterials: (params?: UncodedMaterialListQuery) =>
    apiClient
      .get<Blob>('/purchase-materials/export-uncoded', { params, responseType: 'blob' })
      .then((r) => r.data),
  uncodedMaterials: (params?: UncodedMaterialListQuery) =>
    apiClient
      .get<Page<PurchaseMaterial>>('/purchase-materials', { params: { ...params, coded: false } })
      .then((r) => r.data),
  records: (params?: PurchaseRecordListQuery) =>
    apiClient.get<Page<PurchaseRecord>>('/purchase-records', { params }).then((r) => r.data),
  batchUpdateRecords: (payload: PurchaseRecordBatchUpdate) =>
    apiClient.patch<PurchaseRecord[]>('/purchase-records/batch', payload).then((r) => r.data),
  recordFilterOptions: () =>
    apiClient
      .get<PurchaseRecordFilterOptions>('/purchase-records/filter-options')
      .then((r) => r.data),
  exportRecordResults: (payload: PurchaseRecordResultExportRequest) =>
    apiClient
      .post<Blob>('/purchase-records/export-results', payload, { responseType: 'blob' })
      .then((r) => r.data),
  record: (lineId: number) =>
    apiClient.get<PurchaseRecord>(`/purchase-records/${lineId}`).then((r) => r.data),
  restoreRecordToPlan: (lineId: number, version: number) =>
    apiClient
      .post<PurchaseMaterial>(`/purchase-records/${lineId}/restore-to-plan`, null, {
        headers: { 'If-Match': String(version) },
      })
      .then((r) => r.data),
  updateRecord: (lineId: number, payload: PurchaseRecordWrite) =>
    apiClient.patch<PurchaseRecord>(`/purchase-records/${lineId}`, payload).then((r) => r.data),
}
