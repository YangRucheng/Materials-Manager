from typing import Annotated

from fastapi import APIRouter
from fastapi import Path as FPath
from fastapi.responses import FileResponse

from app.core.permissions import CurrentUser, DbSession
from app.schemas import ExcelExportJobRead, FileId
from app.services import excel_export_job_service, excel_export_service

router = APIRouter(prefix="/excel-export-jobs", tags=["导出任务"])


@router.get("/{job_id}", response_model=ExcelExportJobRead)
async def get_export_job(
    session: DbSession,
    user: CurrentUser,
    job_id: Annotated[int, FPath(ge=1)],
) -> ExcelExportJobRead:
    return await excel_export_job_service.get_export_job(session, job_id=job_id, user=user)


@router.get("/files/{file_uuid}", response_class=FileResponse)
async def download_export_file_by_uuid(session: DbSession, file_uuid: FileId) -> FileResponse:
    # 匿名读取是刻意设计：前端 <a href> 原生下载无法携带 Authorization 头。
    # 安全性依赖 file_uuid 为 UUIDv7（不可猜解）+ 文件只存在于 exports 目录（保留期后删除），
    # 与图片匿名读取同一信任模型（见 files.py read_image 注释）。
    path, download_filename = await excel_export_job_service.get_export_file_by_uuid(
        session, file_uuid=file_uuid
    )
    return FileResponse(
        path=path,
        filename=download_filename,
        media_type=excel_export_service.XLSX_CONTENT_TYPE,
    )
