import { ref, type Ref } from 'vue'
import { AppError } from '@/api/client'
import type { ExcelExportJob } from '@/api/generated'

export interface UseExportJobOptions<TPayload> {
  /** 提交导出参数并返回任务（202 秒回，可能抛业务错误如 ARCHIVED_PURCHASE_PLAN_FORBIDDEN） */
  start: (payload: TPayload) => Promise<ExcelExportJob>
  /** 轮询单个任务状态 */
  poll: (jobId: number) => Promise<ExcelExportJob>
  /** 轮询间隔（毫秒），默认 1500 */
  intervalMs?: number
}

export interface UseExportJob<TPayload> {
  /** 是否正在导出中（提交 + 轮询期间为 true） */
  running: Ref<boolean>
  /** 执行一次导出：提交 → 轮询到终态 → 成功返回 job / 失败抛 AppError */
  run: (payload: TPayload) => Promise<ExcelExportJob>
}

/**
 * 异步导出任务的统一轮询逻辑（申购记录 / 申购计划共用）。
 * 后端导出已异步化（含图片渲染耗时较长）：提交秒回 202 + job id，
 * 前端轮询到 SUCCEEDED/FAILED，终态后由调用方下载文件。
 */
export function useExportJob<TPayload>(
  options: UseExportJobOptions<TPayload>,
): UseExportJob<TPayload> {
  const { start, poll, intervalMs = 1500 } = options
  const running = ref(false)

  const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

  async function run(payload: TPayload): Promise<ExcelExportJob> {
    running.value = true
    try {
      let current = await start(payload)
      while (current.status === 'PENDING' || current.status === 'RUNNING') {
        await sleep(intervalMs)
        current = await poll(current.id)
      }
      if (current.status === 'FAILED') {
        throw new AppError({
          code: current.error_code ?? 'EXPORT_FAILED',
          message: current.error_message ?? '导出失败',
          request_id: '',
        })
      }
      return current
    } finally {
      running.value = false
    }
  }

  return { running, run }
}
