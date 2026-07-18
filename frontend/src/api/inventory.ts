import { apiClient } from './client'
import type {
  DashboardSummary,
  InventoryBalance,
  OperationUpdate,
  OperationWrite,
  Page,
  ReplenishmentPolicy,
  StockMaterial,
  StockMaterialWrite,
  StockOperation,
} from './generated'

export const inventoryApi = {
  summary: () => apiClient.get<DashboardSummary>('/dashboard/summary').then((r) => r.data),
  materials: (params?: Record<string, unknown>) =>
    apiClient.get<Page<StockMaterial>>('/stock-materials', { params }).then((r) => r.data),
  material: (id: number) =>
    apiClient.get<StockMaterial>(`/stock-materials/${id}`).then((r) => r.data),
  createMaterial: (payload: StockMaterialWrite) =>
    apiClient.post<StockMaterial>('/stock-materials', payload).then((r) => r.data),
  updateMaterial: (id: number, payload: StockMaterialWrite) =>
    apiClient.patch<StockMaterial>(`/stock-materials/${id}`, payload).then((r) => r.data),
  disableMaterial: (id: number) =>
    apiClient.post<StockMaterial>(`/stock-materials/${id}/disable`).then((r) => r.data),
  savePolicy: (id: number, payload: ReplenishmentPolicy & { version?: number }) =>
    apiClient
      .put<StockMaterial>(`/stock-materials/${id}/replenishment-policy`, payload)
      .then((r) => r.data),
  balances: (params?: Record<string, unknown>) =>
    apiClient.get<Page<InventoryBalance>>('/inventory/balances', { params }).then((r) => r.data),
  balance: (materialId: number) =>
    apiClient.get<InventoryBalance>(`/inventory/balances/${materialId}`).then((r) => r.data),
  lowStock: (params?: Record<string, unknown>) =>
    apiClient.get<Page<InventoryBalance>>('/inventory/low-stock', { params }).then((r) => r.data),
  inbound: (payload: OperationWrite) =>
    apiClient.post<StockOperation>('/inventory/inbounds', payload).then((r) => r.data),
  outbound: (payload: OperationWrite) =>
    apiClient.post<StockOperation>('/inventory/outbounds', payload).then((r) => r.data),
  operations: (params?: Record<string, unknown>) =>
    apiClient.get<Page<StockOperation>>('/inventory/operations', { params }).then((r) => r.data),
  operation: (id: number) =>
    apiClient.get<StockOperation>(`/inventory/operations/${id}`).then((r) => r.data),
  updateOperation: (id: number, payload: OperationUpdate) =>
    apiClient.patch<StockOperation>(`/inventory/operations/${id}`, payload).then((r) => r.data),
  reverseOperation: (id: number, payload: { client_request_id: string; reason: string }) =>
    apiClient
      .post<StockOperation>(`/inventory/operations/${id}/reverse`, payload)
      .then((r) => r.data),
  replenish: (id: number) =>
    apiClient
      .post<{ next: 'purchase_material'; resource_id: number }>(
        `/inventory/low-stock/${id}/create-replenishment-draft`,
      )
      .then((r) => r.data),
}
