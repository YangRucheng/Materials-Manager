"""Excel 导出任务：异步化结果导出（申购记录 / 申购计划共用）。

接口层只负责登记任务并返回 202，真正的查库 + openpyxl 渲染（嵌入图片，CPU 密集）
放到后台 asyncio 任务里执行（渲染走 asyncio.to_thread），请求秒回。任务生命周期
PENDING → RUNNING → SUCCEEDED | FAILED 持久化在 excel_export_job 表，前端轮询
状态端点获取进度/结果，终态后经下载端点取文件。

临时文件处理约定（与导入相反：导出是“生成文件”方向）：
- 处理器把渲染结果写入目标路径（内部先写 .tmp 再原子改名，失败不留完成态文件）。
- 中途失败：任务置 FAILED 并记录错误，_run_job 的 finally 立即删除目标文件。
- 成功：文件保留供下载（可重复下载），超过保留期由 cleanup_finished_exports 删除。
- 重启残留：mark_stale_exports_failed 把遗留 PENDING/RUNNING 置 FAILED 并删文件。

下载约定（匿名 uuid 链接）：
- 文件命名即 `{uuid7}.xlsx`，`ExcelExportJobRead.file_uuid` 由 file_path 派生返回。
- 下载端点 GET /excel-export-jobs/files/{file_uuid} 不鉴权（浏览器原生下载无法带
  Authorization 头），安全性依赖 uuid7 不可猜解 + 文件仅存在于 exports 目录，
  与图片匿名读取同一信任模型。状态轮询端点仍鉴权并做属主校验。
- 任务不可见/未终态/文件过期分别报错（下载按 uuid 解析，不做属主校验）。

处理器约定：各业务模块提供
    async def process_xxx_export(target_path: Path) -> dict[str, object]
其中返回字典必须含 "download_filename"（下载文件名），可含 rows / image_count 等元信息。
本模块对业务完全无感知。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.core.identifiers import uuid7_string
from app.domain.enums import ExcelExportJobStatus, Role
from app.models import ExcelExportJob, User
from app.schemas import ExcelExportJobRead
from app.services.common import utcnow

logger = logging.getLogger(__name__)

ExportProcessor = Callable[[Path], Awaitable[dict[str, object]]]

EXPORT_DIR_NAME = "exports"
# 成功文件的保留期：超过后由清理任务删除行与文件。
EXPORT_RETENTION_DAYS = 3

# 保持对运行中任务的引用，防止被 GC 回收（单 worker 进程内有效）。
_running_tasks: set[asyncio.Task[None]] = set()

_INTERRUPTED_STATUSES = (ExcelExportJobStatus.PENDING, ExcelExportJobStatus.RUNNING)
_TERMINAL_STATUSES = (ExcelExportJobStatus.SUCCEEDED, ExcelExportJobStatus.FAILED)


def exports_dir() -> Path:
    directory = settings.upload_dir / EXPORT_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def new_export_target() -> Path:
    """生成导出文件目标路径（exports 目录下，uuid7 命名，后缀 .xlsx）。"""
    return exports_dir() / f"{uuid7_string()}.xlsx"


async def enqueue_export(
    *,
    export_type: str,
    params: dict[str, object] | None,
    processor: ExportProcessor,
    created_by: int | None,
) -> ExcelExportJobRead:
    """登记 PENDING 任务并启动后台执行。导出只读不改数据，允许并发，不做 409 限制。"""
    async with SessionLocal() as session:
        job = ExcelExportJob(
            export_type=export_type,
            status=ExcelExportJobStatus.PENDING,
            params=params,
            created_by=created_by,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
    task = asyncio.create_task(_run_job(job.id, processor), name=f"export-job-{job.id}")
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return ExcelExportJobRead.model_validate(job)


def _visible_to(job: ExcelExportJob, user: User) -> bool:
    """任务可见性：创建者本人或超级管理员。"""
    return job.created_by is None or job.created_by == user.id or user.role == Role.SUPER_ADMIN


async def get_export_job(
    session: AsyncSession, *, job_id: int, user: User
) -> ExcelExportJobRead:
    job = await session.get(ExcelExportJob, job_id)
    if job is None or not _visible_to(job, user):
        raise AppError("NOT_FOUND", "导出任务不存在")
    return ExcelExportJobRead.model_validate(job)


async def get_export_file_by_uuid(
    session: AsyncSession, *, file_uuid: str
) -> tuple[Path, str]:
    """按文件 uuid 返回（文件路径, 下载文件名）；供匿名下载端点使用。

    下载链接不鉴权是刻意设计（浏览器原生下载无法带 Authorization 头），安全性
    依赖 uuid7 不可猜解 + 文件只存在于 exports 目录（保留期后删除）。
    以文件是否存在为准：导出文件为原子写盘（先 .tmp 再改名），存在即完整可用；
    任务行仅用于提供友好下载名，行缺失/路径漂移时回退 uuid 命名仍可下载。
    文件缺失时记录诊断日志（uuid、任务行是否存在及状态），便于线上排查。
    """
    path = exports_dir() / f"{file_uuid}.xlsx"
    job = await session.scalar(
        select(ExcelExportJob).where(ExcelExportJob.file_path == str(path))
    )
    if not path.is_file():
        logger.warning(
            "export file missing on download file_uuid=%s job_exists=%s job_status=%s",
            file_uuid,
            job is not None,
            job.status.value if job is not None else None,
        )
        raise AppError("EXPORT_FILE_EXPIRED", "导出文件已过期或不存在，请重新导出")
    download_filename = (
        job.download_filename
        if job is not None and job.download_filename
        else f"export_{file_uuid}.xlsx"
    )
    return path, download_filename


async def mark_stale_exports_failed() -> int:
    """启动时清理：重启前遗留的 PENDING/RUNNING 任务标记失败并删除临时文件。"""
    async with SessionLocal() as session:
        stale_paths = [
            path
            for path in (
                await session.scalars(
                    select(ExcelExportJob.file_path).where(
                        ExcelExportJob.status.in_(_INTERRUPTED_STATUSES)
                    )
                )
            ).all()
            if path is not None
        ]
        if stale_paths:
            now = utcnow()
            await session.execute(
                update(ExcelExportJob)
                .where(ExcelExportJob.status.in_(_INTERRUPTED_STATUSES))
                .values(
                    status=ExcelExportJobStatus.FAILED,
                    error_code="SERVER_RESTARTED",
                    error_message="服务重启，导出任务已中断",
                    finished_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
    for path in stale_paths:
        await asyncio.to_thread(Path(path).unlink, missing_ok=True)
    return len(stale_paths)


async def cleanup_finished_exports(*, retention_days: int = EXPORT_RETENTION_DAYS) -> int:
    """定期清理：删除 retention_days 天前已终态（SUCCEEDED/FAILED）的任务行及其文件。

    成功文件靠这里收敛：任务行与文件同生共死，删除行即删除文件。
    顺带清除 exports 目录下残留的 .tmp 孤儿文件（原子写盘在改名前进程崩溃所致）。
    """
    cutoff = utcnow() - timedelta(days=retention_days)
    async with SessionLocal() as session:
        expired = list(
            (
                await session.scalars(
                    select(ExcelExportJob)
                    .where(
                        ExcelExportJob.status.in_(_TERMINAL_STATUSES),
                        ExcelExportJob.finished_at < cutoff,
                    )
                )
            ).all()
        )
        if expired:
            await session.execute(
                delete(ExcelExportJob).where(
                    ExcelExportJob.id.in_([job.id for job in expired])
                )
            )
            await session.commit()
    for job in expired:
        if job.file_path:
            await asyncio.to_thread(Path(job.file_path).unlink, missing_ok=True)

    def _sweep_orphan_tmp() -> int:
        directory = settings.upload_dir / EXPORT_DIR_NAME
        if not directory.is_dir():
            return 0
        removed = 0
        tmp_cutoff = time.time() - 24 * 60 * 60
        for path in directory.glob("*.tmp"):
            try:
                if path.stat().st_mtime < tmp_cutoff:
                    path.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                continue
        return removed

    await asyncio.to_thread(_sweep_orphan_tmp)
    return len(expired)


async def run_cleanup_worker(stop_event: asyncio.Event) -> None:
    """每日保留期清理循环（与 webhook/计划清理 worker 同一范式）。"""
    while not stop_event.is_set():
        try:
            purged = await cleanup_finished_exports()
            if purged:
                logger.info("purged %s expired excel export jobs", purged)
        except Exception:
            logger.exception("excel export cleanup worker crashed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=24 * 60 * 60)
        except TimeoutError:
            pass


async def _run_job(job_id: int, processor: ExportProcessor) -> None:
    """后台执行：置 RUNNING → 运行处理器 → 写结果/错误 → 失败时清理目标文件。"""
    async with SessionLocal() as session:
        job = await session.get(ExcelExportJob, job_id)
        if job is None:
            return
        job.status = ExcelExportJobStatus.RUNNING
        job.started_at = utcnow()
        file_path = Path(job.file_path) if job.file_path else new_export_target()
        job.file_path = str(file_path)
        await session.commit()

    result: dict[str, object] | None = None
    download_filename: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    try:
        result = await processor(file_path)
        if not isinstance(result, dict) or not result.get("download_filename"):
            raise AppError("INTERNAL_EXPORT_ERROR", "导出任务未返回有效结果")
        download_filename = str(result["download_filename"])[:255]
    except AppError as exc:
        error_code = exc.code
        error_message = exc.message[:1000]
        logger.warning("export job failed job_id=%s code=%s", job_id, error_code)
    except Exception:
        error_code = "INTERNAL_EXPORT_ERROR"
        error_message = "导出任务发生未知错误"
        logger.exception("export job crashed job_id=%s", job_id)
    finally:
        async with SessionLocal() as session:
            job = await session.get(ExcelExportJob, job_id)
            if job is not None:
                job.status = (
                    ExcelExportJobStatus.SUCCEEDED
                    if error_code is None
                    else ExcelExportJobStatus.FAILED
                )
                job.download_filename = download_filename
                job.result = result
                job.error_code = error_code
                job.error_message = error_message
                job.finished_at = utcnow()
                await session.commit()
        if error_code is not None:
            # 失败即删：不留残缺/完成态文件；成功则保留至保留期由清理任务收敛。
            await asyncio.to_thread(file_path.unlink, missing_ok=True)
