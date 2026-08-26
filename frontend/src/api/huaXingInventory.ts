import { apiClient } from './client'
import type {
  ExcelImportJob,
  HuaXingFilterOptions,
  HuaXingInventory,
  LastImport,
  Page,
  PagedQueryParams,
} from './generated'

/** 华星库存列表查询（申购部门/申购人为多选，| 分隔后精确匹配） */
export interface HuaXingInventoryListQuery extends PagedQueryParams {
  material_code?: string
  name?: string
  model_spec?: string
  purchase_department?: string
  purchaser?: string
}

export const huaXingInventoryApi = {
  list: (params?: HuaXingInventoryListQuery) =>
    apiClient.get<Page<HuaXingInventory>>('/huaxing-inventory', { params }).then((r) => r.data),
  filterOptions: () =>
    apiClient.get<HuaXingFilterOptions>('/huaxing-inventory/filter-options').then((r) => r.data),
  import: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient
      .post<ExcelImportJob>('/huaxing-inventory/import', formData, { timeout: 120_000 })
      .then((r) => r.data)
  },
  importJob: (jobId: number) =>
    apiClient.get<ExcelImportJob>(`/huaxing-inventory/import-jobs/${jobId}`).then((r) => r.data),
  lastImport: () => apiClient.get<LastImport>('/huaxing-inventory/last-import').then((r) => r.data),
}
