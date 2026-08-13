from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile
from fastapi import Path as FPath

from app.api.deps import PageNo, PageSize
from app.core.errors import AppError
from app.core.permissions import CurrentUser, DbSession, PurchaseWriter
from app.schemas import ExcelImportJobRead, LastImportRead, MaterialCodeLibraryRead, Page
from app.services import import_job_service, material_code_library_service

router = APIRouter(prefix="/material-code-library", tags=["物料编码库"])

JOB_TYPE = "MATERIAL_CODE_LIBRARY"


@router.get("", response_model=Page[MaterialCodeLibraryRead])
async def list_material_codes(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: Annotated[str | None, Query(max_length=255)] = None,
    name: Annotated[str | None, Query(max_length=128)] = None,
    model_spec: Annotated[str | None, Query(max_length=255)] = None,
    material_code: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[MaterialCodeLibraryRead]:
    items, total = await material_code_library_service.search_material_codes(
        session,
        keyword=keyword,
        name=name,
        model_spec=model_spec,
        material_code=material_code,
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
async def import_material_codes(
    file: Annotated[UploadFile, File(...)],
    user: PurchaseWriter,
) -> ExcelImportJobRead:
    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")):
        raise AppError("UNSUPPORTED_EXCEL_FILE", "仅支持 .xlsx 或 .xlsm 格式的 Excel 文件")
    file_path: Path | None = None
    try:
        file_path = await import_job_service.save_upload(
            file, max_bytes=material_code_library_service.MAX_IMPORT_BYTES
        )
        return await import_job_service.enqueue_import(
            import_type=JOB_TYPE,
            original_filename=file.filename or "import.xlsx",
            file_path=file_path,
            processor=material_code_library_service.process_import_file,
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
