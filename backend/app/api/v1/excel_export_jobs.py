from typing import Annotated

from fastapi import APIRouter
from fastapi import Path as FPath
from fastapi.responses import FileResponse

from app.core.permissions import CurrentUser, DbSession
from app.schemas import ExcelExportJobRead
from app.services import excel_export_job_service, excel_export_service

router = APIRouter(prefix="/excel-export-jobs", tags=["导出任务"])


@router.get("/{job_id}", response_model=ExcelExportJobRead)
async def get_export_job(
    session: DbSession,
    user: CurrentUser,
    job_id: Annotated[int, FPath(ge=1)],
) -> ExcelExportJobRead:
    return await excel_export_job_service.get_export_job(session, job_id=job_id, user=user)


@router.get("/{job_id}/file")
async def download_export_job_file(
    session: DbSession,
    user: CurrentUser,
    job_id: Annotated[int, FPath(ge=1)],
) -> FileResponse:
    path, download_filename = await excel_export_job_service.get_export_file(
        session, job_id=job_id, user=user
    )
    return FileResponse(
        path=path,
        filename=download_filename,
        media_type=excel_export_service.XLSX_CONTENT_TYPE,
    )
