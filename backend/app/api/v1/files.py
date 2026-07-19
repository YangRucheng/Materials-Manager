from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.core.permissions import DbSession, require_roles
from app.domain.enums import Role
from app.models import User
from app.schemas import FileId, FileObjectRead
from app.services import file_service

router = APIRouter(prefix="/files/images", tags=["图片"])
CACHE_CONTROL = "public, max-age=86400, s-maxage=2592000"
FileWriter = Annotated[
    User,
    Depends(require_roles(Role.SUPER_ADMIN, Role.WAREHOUSE_ADMIN, Role.PURCHASE_ADMIN)),
]


@router.post("", response_model=FileObjectRead, status_code=status.HTTP_201_CREATED)
async def upload(file: UploadFile, session: DbSession, user: FileWriter) -> FileObjectRead:
    return await file_service.save_image(session, file, user.id)


@router.get("/{file_id}")
async def read_image(
    file_id: FileId,
    session: DbSession,
    size: Annotated[int | None, Query(ge=16, le=2048)] = None,
) -> Response:
    item, path = await file_service.get_image(session, file_id)
    headers = {"Cache-Control": CACHE_CONTROL}
    if size is not None:
        return Response(
            content=await file_service.render_preview(path, size),
            media_type=file_service.PREVIEW_MIME_TYPE,
            headers=headers,
        )
    return FileResponse(
        path,
        media_type=item.mime_type,
        filename=item.file_name,
        content_disposition_type="inline",
        headers=headers,
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(file_id: FileId, session: DbSession, user: FileWriter) -> Response:
    await file_service.delete_image(session, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
