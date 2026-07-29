from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile

from app.core.errors import AppError
from app.core.permissions import CurrentUser, DbSession, PurchaseWriter
from app.schemas import MaterialCodeLibraryImportRead, MaterialCodeLibraryRead, Page
from app.services import material_code_library_service

router = APIRouter(prefix="/material-code-library", tags=["物料编码库"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]


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


@router.post("/import", response_model=MaterialCodeLibraryImportRead)
async def import_material_codes(
    session: DbSession,
    user: PurchaseWriter,
    file: Annotated[UploadFile, File(...)],
) -> MaterialCodeLibraryImportRead:
    filename = (file.filename or "").lower()
    try:
        if not filename.endswith((".xlsx", ".xlsm")):
            raise AppError("UNSUPPORTED_EXCEL_FILE", "仅支持 .xlsx 或 .xlsm 格式的 Excel 文件")
        content = await file.read(material_code_library_service.MAX_IMPORT_BYTES + 1)
        return await material_code_library_service.replace_material_codes(session, content)
    finally:
        await file.close()
