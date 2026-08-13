"""Excel 导入任务：异步化导入（物料编码库 / 华星库存共用）。

接口层只负责上传落盘 + 登记任务并返回 202，真正的解析与全量替换放到后台
asyncio 任务里执行，请求秒回，避免 CDN/nginx 回源超时。任务生命周期
PENDING → RUNNING → SUCCEEDED | FAILED 持久化在 excel_import_job 表，
前端轮询状态端点获取进度/结果。启动时把残留 PENDING/RUNNING 任务标记失败。

处理器约定：各模块 service 提供
    async def process_import_file(file_path: Path) -> dict[str, object]
其中 (a) 解析用 await asyncio.to_thread(同步解析器, file_path)（openpyxl 同步且
CPU 密集，不能占用事件循环）；(b) 数据表事务在处理器自己的 SessionLocal 会话里
完成（DELETE 全表 + 分批 INSERT + 单次 commit）。本模块对业务完全无感知。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.core.identifiers import uuid7_string
from app.domain.enums import ExcelImportJobStatus
from app.models import ExcelImportJob
from app.schemas import ExcelImportJobRead
from app.services.common import utcnow

logger = logging.getLogger(__name__)

ImportProcessor = Callable[[Path], Awaitable[dict[str, object]]]

IMPORT_DIR_NAME = "imports"
CHUNK_SIZE = 1024 * 1024

# 保持对运行中任务的引用，防止被 GC 回收（单 worker 进程内有效）。
_running_tasks: set[asyncio.Task[None]] = set()
# 按 import_type 串行化「检查进行中 + 登记」两步，保证 409 判断原子（单 worker 内）。
_type_locks: dict[str, asyncio.Lock] = {}

_INTERRUPTED_STATUSES = (ExcelImportJobStatus.PENDING, ExcelImportJobStatus.RUNNING)


def _type_lock(import_type: str) -> asyncio.Lock:
    """取/建按类型串行化用的锁；事件循环变化时重建（测试按用例换 loop）。"""
    loop = asyncio.get_running_loop()
    lock = _type_locks.get(import_type)
    if lock is None or getattr(lock, "_loop", None) not in (None, loop):
        lock = asyncio.Lock()
        _type_locks[import_type] = lock
    return lock


async def save_upload(upload: UploadFile, *, max_bytes: int) -> Path:
    """把上传文件流式写到临时目录，超限报 EXCEL_FILE_TOO_LARGE。"""
    filename = upload.filename or "upload.xlsx"
    suffix = Path(filename).suffix.lower() or ".xlsx"
    import_dir = settings.upload_dir / IMPORT_DIR_NAME
    import_dir.mkdir(parents=True, exist_ok=True)
    target = import_dir / f"{uuid7_string()}{suffix}"

    def _stream_to_disk() -> None:
        total = 0
        with open(target, "wb") as fh:
            while True:
                chunk = upload.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppError("EXCEL_FILE_TOO_LARGE", "Excel 文件不能超过 50 MB")
                fh.write(chunk)

    try:
        await asyncio.to_thread(_stream_to_disk)
    except BaseException:
        await asyncio.to_thread(target.unlink, missing_ok=True)
        raise
    return target


async def enqueue_import(
    *,
    import_type: str,
    original_filename: str,
    file_path: Path,
    processor: ImportProcessor,
    created_by: int | None,
) -> ExcelImportJobRead:
    """登记 PENDING 任务并启动后台执行；同类任务进行中时报 409。"""
    async with _type_lock(import_type):
        async with SessionLocal() as session:
            active = await session.scalar(
                select(ExcelImportJob.id)
                .where(
                    ExcelImportJob.import_type == import_type,
                    ExcelImportJob.status.in_(_INTERRUPTED_STATUSES),
                )
                .limit(1)
            )
            if active is not None:
                raise AppError(
                    "IMPORT_IN_PROGRESS",
                    "同类导入任务正在进行中，请稍后再试",
                    status_code=409,
                )
            job = ExcelImportJob(
                import_type=import_type,
                status=ExcelImportJobStatus.PENDING,
                original_filename=original_filename[:255],
                file_path=str(file_path),
                created_by=created_by,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
    task = asyncio.create_task(_run_job(job.id, processor), name=f"import-job-{job.id}")
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return ExcelImportJobRead.model_validate(job)


async def get_import_job(
    session: AsyncSession, *, import_type: str, job_id: int
) -> ExcelImportJobRead:
    job = await session.scalar(
        select(ExcelImportJob).where(
            ExcelImportJob.id == job_id,
            ExcelImportJob.import_type == import_type,
        )
    )
    if job is None:
        raise AppError("NOT_FOUND", "导入任务不存在")
    return ExcelImportJobRead.model_validate(job)


async def mark_stale_jobs_failed() -> int:
    """启动时清理：重启前遗留的 PENDING/RUNNING 任务标记失败并删除临时文件。"""
    async with SessionLocal() as session:
        stale_paths = list(
            (
                await session.scalars(
                    select(ExcelImportJob.file_path).where(
                        ExcelImportJob.status.in_(_INTERRUPTED_STATUSES)
                    )
                )
            ).all()
        )
        if stale_paths:
            now = utcnow()
            await session.execute(
                update(ExcelImportJob)
                .where(ExcelImportJob.status.in_(_INTERRUPTED_STATUSES))
                .values(
                    status=ExcelImportJobStatus.FAILED,
                    error_code="SERVER_RESTARTED",
                    error_message="服务重启，导入任务已中断",
                    finished_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
    for path in stale_paths:
        await asyncio.to_thread(Path(path).unlink, missing_ok=True)
    return len(stale_paths)


async def _run_job(job_id: int, processor: ImportProcessor) -> None:
    """后台执行：置 RUNNING → 运行处理器 → 写结果/错误 → 清理临时文件。"""
    async with SessionLocal() as session:
        job = await session.get(ExcelImportJob, job_id)
        if job is None:
            return
        job.status = ExcelImportJobStatus.RUNNING
        job.started_at = utcnow()
        file_path = Path(job.file_path)
        await session.commit()

    result: dict[str, object] | None = None
    error_code: str | None = None
    error_message: str | None = None
    try:
        result = await processor(file_path)
    except AppError as exc:
        error_code = exc.code
        error_message = exc.message[:1000]
        logger.warning("import job failed job_id=%s code=%s", job_id, error_code)
    except Exception:
        error_code = "INTERNAL_IMPORT_ERROR"
        error_message = "导入任务发生未知错误"
        logger.exception("import job crashed job_id=%s", job_id)
    finally:
        async with SessionLocal() as session:
            job = await session.get(ExcelImportJob, job_id)
            if job is not None:
                job.status = (
                    ExcelImportJobStatus.SUCCEEDED
                    if error_code is None
                    else ExcelImportJobStatus.FAILED
                )
                job.result = result
                job.error_code = error_code
                job.error_message = error_message
                job.finished_at = utcnow()
                await session.commit()
        await asyncio.to_thread(file_path.unlink, missing_ok=True)
