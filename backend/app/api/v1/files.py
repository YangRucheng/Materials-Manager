from typing import Annotated

from fastapi import APIRouter, Depends, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.core.permissions import CurrentUser, DbSession, require_roles
from app.domain.enums import Role
from app.models import User
from app.schemas import FileObjectRead
from app.services import file_service

router = APIRouter(prefix="/files/images", tags=["图片"])
FileWriter = Annotated[
    User,
    Depends(require_roles(Role.SUPER_ADMIN, Role.WAREHOUSE_ADMIN, Role.PURCHASE_ADMIN)),
]


@router.post("", response_model=FileObjectRead, status_code=status.HTTP_201_CREATED)
async def upload(file: UploadFile, session: DbSession, user: FileWriter) -> FileObjectRead:
    return await file_service.save_image(session, file, user.id)


@router.get("/{file_id}", response_class=FileResponse)
async def read_image(file_id: int, session: DbSession, user: CurrentUser) -> FileResponse:
    item, path = await file_service.get_image(session, file_id)
    return FileResponse(path, media_type="image/png", filename=item.file_name)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(file_id: int, session: DbSession, user: FileWriter) -> Response:
    await file_service.delete_image(session, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
