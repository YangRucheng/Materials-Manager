import { describe, expect, it, vi } from 'vitest'
import type { ExcelExportJob } from '@/api/generated'
import { useExportJob } from './useExportJob'

const job = (id: number, status: ExcelExportJob['status']): ExcelExportJob => ({
  id,
  export_type: 'PURCHASE_PLAN_RESULTS',
  status,
  download_filename: '申购计划导出.xlsx',
  result: { rows: 3 },
  created_at: '2026-08-16T00:00:00Z',
})

describe('useExportJob', () => {
  it('polls until succeeded and returns the job', async () => {
    const poll = vi.fn<(jobId: number) => Promise<ExcelExportJob>>()
    poll.mockResolvedValueOnce(job(1, 'RUNNING')).mockResolvedValueOnce(job(1, 'SUCCEEDED'))
    const { running, run } = useExportJob({
      start: async () => job(1, 'PENDING'),
      poll,
      intervalMs: 1,
    })

    const result = await run({ columns: ['name'] })

    expect(result.status).toBe('SUCCEEDED')
    expect(result.download_filename).toBe('申购计划导出.xlsx')
    expect(poll).toHaveBeenCalledTimes(2)
    expect(running.value).toBe(false)
  })

  it('rejects with the job error when it fails', async () => {
    const { run } = useExportJob({
      start: async () => job(1, 'PENDING'),
      poll: async () => ({
        ...job(1, 'FAILED'),
        error_code: 'EXPORT_RESULT_LIMIT_EXCEEDED',
        error_message: '查询结果超过 10000 行，请缩小筛选范围后导出',
      }),
      intervalMs: 1,
    })

    await expect(run({ columns: ['name'] })).rejects.toMatchObject({
      code: 'EXPORT_RESULT_LIMIT_EXCEEDED',
      message: '查询结果超过 10000 行，请缩小筛选范围后导出',
    })
  })

  it('propagates start errors such as ARCHIVED_PURCHASE_PLAN_FORBIDDEN', async () => {
    const { run } = useExportJob({
      start: async () => {
        throw new Error('ARCHIVED_PURCHASE_PLAN_FORBIDDEN')
      },
      poll: async () => job(1, 'SUCCEEDED'),
    })

    await expect(run({ columns: ['name'] })).rejects.toThrow('ARCHIVED_PURCHASE_PLAN_FORBIDDEN')
  })
})
