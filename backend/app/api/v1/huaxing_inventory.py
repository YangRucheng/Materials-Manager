from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile
from fastapi import Path as FPath

from app.api.deps import PageNo, PageSize
from app.core.errors import AppError
from app.core.permissions import CurrentUser, DbSession, WarehouseWriter
from app.schemas import (
    ExcelImportJobRead,
    HuaXingFilterOptions,
    HuaXingInventoryRead,
    LastImportRead,
    Page,
)
from app.services import huaxing_inventory_service, import_job_service
from app.services.import_file_reader import SUPPORTED_IMPORT_SUFFIXES

router = APIRouter(prefix="/huaxing-inventory", tags=["华星库存"])

JOB_TYPE = "HUAXING_INVENTORY"


@router.get("", response_model=Page[HuaXingInventoryRead])
async def list_huaxing_inventory(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    material_code: Annotated[str | None, Query(max_length=64)] = None,
    name: Annotated[str | None, Query(max_length=255)] = None,
    model_spec: Annotated[str | None, Query(max_length=255)] = None,
    purchase_department: Annotated[str | None, Query(max_length=128)] = None,
    purchaser: Annotated[str | None, Query(max_length=128)] = None,
) -> Page[HuaXingInventoryRead]:
    """华星总库存列表查询（文本字段内多关键词按 | 分隔做 OR；申购部门/申购人为精确多值筛选）。"""
    items, total = await huaxing_inventory_service.search_huaxing_inventory(
        session,
        material_code=material_code,
        name=name,
        model_spec=model_spec,
        purchase_department=purchase_department,
        purchaser=purchaser,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/filter-options", response_model=HuaXingFilterOptions)
async def filter_options(
    session: DbSession,
    user: CurrentUser,
) -> HuaXingFilterOptions:
    """华星库存筛选下拉选项（申购部门/申购人 distinct 值）。"""
    purchase_departments, purchasers = await huaxing_inventory_service.list_huaxing_filter_options(
        session
    )
    return HuaXingFilterOptions(
        purchase_departments=purchase_departments,
        purchasers=purchasers,
    )


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
async def import_huaxing_inventory(
    file: Annotated[UploadFile, File(...)],
    user: WarehouseWriter,
) -> ExcelImportJobRead:
    filename = (file.filename or "").lower()
    if not filename.endswith(SUPPORTED_IMPORT_SUFFIXES):
        raise AppError("UNSUPPORTED_EXCEL_FILE", "仅支持 .xls、.xlsx 或 .csv 格式的表格文件")
    file_path: Path | None = None
    try:
        file_path = await import_job_service.save_upload(
            file, max_bytes=huaxing_inventory_service.MAX_IMPORT_BYTES
        )
        return await import_job_service.enqueue_import(
            import_type=JOB_TYPE,
            original_filename=file.filename or "import.xlsx",
            file_path=file_path,
            processor=huaxing_inventory_service.process_import_file,
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
