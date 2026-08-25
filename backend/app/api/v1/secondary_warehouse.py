from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile
from fastapi import Path as FPath

from app.api.deps import PageNo, PageSize
from app.core.errors import AppError
from app.core.permissions import CurrentUser, DbSession, WarehouseWriter
from app.schemas import ExcelImportJobRead, LastImportRead, LiteInventoryRead, Page
from app.services import import_job_service, lite_inventory_service
from app.services.import_file_reader import SUPPORTED_IMPORT_SUFFIXES

router = APIRouter(prefix="/secondary-warehouse", tags=["二级库"])

JOB_TYPE = "LITE_INVENTORY"


@router.get("", response_model=Page[LiteInventoryRead])
async def list_lite_inventory(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: Annotated[str | None, Query(max_length=255)] = None,
) -> Page[LiteInventoryRead]:
    """精简二级库列表查询（物资名称/型号/备注关键字匹配）。"""
    items, total = await lite_inventory_service.search_lite_inventory(
        session,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/last-import", response_model=LastImportRead)
async def last_import(
    session: DbSession,
    user: CurrentUser,
) -> LastImportRead:
    last_import_at = await import_job_service.latest_import_finished_at(
        session, import_type=JOB_TYPE
    )
    return LastImportRead(last_import_at=last_import_at)


@router.post("/import", response_model=ExcelImportJobRead, status_code=202)
async def import_lite_inventory(
    file: Annotated[UploadFile, File(...)],
    user: WarehouseWriter,
) -> ExcelImportJobRead:
    filename = (file.filename or "").lower()
    if not filename.endswith(SUPPORTED_IMPORT_SUFFIXES):
        raise AppError("UNSUPPORTED_EXCEL_FILE", "仅支持 .xls、.xlsx 或 .csv 格式的表格文件")
    file_path: Path | None = None
    try:
        file_path = await import_job_service.save_upload(
            file, max_bytes=lite_inventory_service.MAX_IMPORT_BYTES
        )
        return await import_job_service.enqueue_import(
            import_type=JOB_TYPE,
            original_filename=file.filename or "import.xlsx",
            file_path=file_path,
            processor=lite_inventory_service.process_import_file,
            created_by=user.id,
        )
    except BaseException:
        if file_path is not None:
            await asyncio.to_thread(file_path.unlink, missing_ok=True)
        raise
    finally:
        await file.close()


@router.get("/import-jobs/{job_id}", response_model=ExcelImportJobRead)
async def get_import_job(
    session: DbSession,
    user: CurrentUser,
    job_id: Annotated[int, FPath(ge=1)],
) -> ExcelImportJobRead:
    return await import_job_service.get_import_job(session, import_type=JOB_TYPE, job_id=job_id)
