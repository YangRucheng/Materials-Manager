import { apiClient } from './client'
import type {
  DashboardSummary,
  InventoryBalance,
  OperationUpdate,
  OperationWrite,
  Page,
  PagedQueryParams,
  ReplenishmentDraftWrite,
  ReplenishmentDefaults,
  ReplenishmentPolicy,
  StockMaterial,
  StockMaterialWrite,
  StockOperation,
} from './generated'

/** 物资档案列表查询 */
export interface StockMaterialListQuery extends PagedQueryParams {
  keyword?: string
}

/** 库存查询（balances / lowStock 共用） */
export interface InventoryBalanceListQuery extends PagedQueryParams {
  keyword?: string
  min_qty?: string
  max_qty?: string
}

/** 操作记录列表查询 */
export interface StockOperationListQuery extends PagedQueryParams {
  operation_no?: string
  operation_type?: string
  material_name?: string
  start_at?: string
  end_at?: string
}

export const inventoryApi = {
  summary: () => apiClient.get<DashboardSummary>('/dashboard/summary').then((r) => r.data),
  materials: (params?: StockMaterialListQuery) =>
    apiClient.get<Page<StockMaterial>>('/stock-materials', { params }).then((r) => r.data),
  material: (id: number) =>
    apiClient.get<StockMaterial>(`/stock-materials/${id}`).then((r) => r.data),
  materialMiniProgramCode: (id: number) =>
    apiClient
      .get<Blob>(`/stock-materials/${id}/mini-program-code`, {
        responseType: 'blob',
      })
      .then((r) => r.data),
  createMaterial: (payload: StockMaterialWrite) =>
    apiClient.post<StockMaterial>('/stock-materials', payload).then((r) => r.data),
  updateMaterial: (id: number, payload: StockMaterialWrite) =>
    apiClient.patch<StockMaterial>(`/stock-materials/${id}`, payload).then((r) => r.data),
  deleteMaterial: (id: number, version: number) =>
    apiClient.delete(`/stock-materials/${id}`, { headers: { 'If-Match': String(version) } }),
  savePolicy: (
    id: number,
    payload: Pick<ReplenishmentPolicy, 'minimum_qty' | 'enabled'> & { version?: number },
  ) =>
    apiClient
      .put<StockMaterial>(`/stock-materials/${id}/replenishment-policy`, payload)
      .then((r) => r.data),
  balances: (params?: InventoryBalanceListQuery) =>
    apiClient.get<Page<InventoryBalance>>('/inventory/balances', { params }).then((r) => r.data),
  balance: (materialId: number) =>
    apiClient.get<InventoryBalance>(`/inventory/balances/${materialId}`).then((r) => r.data),
  lowStock: (params?: InventoryBalanceListQuery) =>
    apiClient.get<Page<InventoryBalance>>('/inventory/low-stock', { params }).then((r) => r.data),
  replenishmentDefaults: () =>
    apiClient.get<ReplenishmentDefaults>('/inventory/replenishment-defaults').then((r) => r.data),
  inbound: (payload: OperationWrite) =>
    apiClient.post<StockOperation>('/inventory/inbounds', payload).then((r) => r.data),
  outbound: (payload: OperationWrite) =>
    apiClient.post<StockOperation>('/inventory/outbounds', payload).then((r) => r.data),
  operations: (params?: StockOperationListQuery) =>
    apiClient.get<Page<StockOperation>>('/inventory/operations', { params }).then((r) => r.data),
  operation: (id: number) =>
    apiClient.get<StockOperation>(`/inventory/operations/${id}`).then((r) => r.data),
  updateOperation: (id: number, payload: OperationUpdate) =>
    apiClient.patch<StockOperation>(`/inventory/operations/${id}`, payload).then((r) => r.data),
  reverseOperation: (
    id: number,
    payload: {
      client_request_id: string
      reason: string
      lines: Array<{ stock_material_id: number; quantity: string }>
    },
  ) =>
    apiClient
      .post<StockOperation>(`/inventory/operations/${id}/reverse`, payload)
      .then((r) => r.data),
  replenish: (id: number, payload: ReplenishmentDraftWrite) =>
    apiClient
      .post<{ next: 'purchase_material'; resource_id: number }>(
        `/inventory/low-stock/${id}/create-replenishment-draft`,
        payload,
      )
      .then((r) => r.data),
}
