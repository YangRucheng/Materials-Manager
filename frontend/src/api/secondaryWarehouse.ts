import { apiClient } from './client'
import type { ExcelImportJob, LastImport, LiteInventory, Page, PagedQueryParams } from './generated'

/** 精简二级库列表查询 */
export interface LiteInventoryListQuery extends PagedQueryParams {
  keyword?: string
}

export const secondaryWarehouseApi = {
  list: (params?: LiteInventoryListQuery) =>
    apiClient.get<Page<LiteInventory>>('/secondary-warehouse', { params }).then((r) => r.data),
  import: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient
      .post<ExcelImportJob>('/secondary-warehouse/import', formData, { timeout: 120_000 })
      .then((r) => r.data)
  },
  importJob: (jobId: number) =>
    apiClient.get<ExcelImportJob>(`/secondary-warehouse/import-jobs/${jobId}`).then((r) => r.data),
  lastImport: () =>
    apiClient.get<LastImport>('/secondary-warehouse/last-import').then((r) => r.data),
}
