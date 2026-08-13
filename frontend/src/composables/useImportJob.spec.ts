import { describe, expect, it, vi } from 'vitest'
import type { ExcelImportJob } from '@/api/generated'
import { useImportJob } from './useImportJob'

const job = (id: number, status: ExcelImportJob['status']): ExcelImportJob => ({
  id,
  import_type: 'HUAXING_INVENTORY',
  status,
  original_filename: 'stock.xlsx',
  result: { imported_count: 5 },
  created_at: '2026-08-13T00:00:00Z',
})

describe('useImportJob', () => {
  it('polls until succeeded and returns the result', async () => {
    const poll = vi.fn<(jobId: number) => Promise<ExcelImportJob>>()
    poll.mockResolvedValueOnce(job(1, 'RUNNING')).mockResolvedValueOnce(job(1, 'SUCCEEDED'))
    const { running, run } = useImportJob({
      start: async () => job(1, 'PENDING'),
      poll,
      intervalMs: 1,
    })

    const result = await run(new File(['x'], 'stock.xlsx'))

    expect(result).toEqual({ imported_count: 5 })
    expect(poll).toHaveBeenCalledTimes(2)
    expect(running.value).toBe(false)
  })

  it('rejects with the job error when it fails', async () => {
    const { run } = useImportJob({
      start: async () => job(1, 'PENDING'),
      poll: async () => ({
        ...job(1, 'FAILED'),
        error_code: 'IMPORT_BAD',
        error_message: '文件损坏',
      }),
      intervalMs: 1,
    })

    await expect(run(new File(['x'], 'stock.xlsx'))).rejects.toMatchObject({
      code: 'IMPORT_BAD',
      message: '文件损坏',
    })
  })

  it('propagates start errors such as IMPORT_IN_PROGRESS', async () => {
    const { run } = useImportJob({
      start: async () => {
        throw new Error('IMPORT_IN_PROGRESS')
      },
      poll: async () => job(1, 'SUCCEEDED'),
    })

    await expect(run(new File(['x'], 'stock.xlsx'))).rejects.toThrow('IMPORT_IN_PROGRESS')
  })
})
