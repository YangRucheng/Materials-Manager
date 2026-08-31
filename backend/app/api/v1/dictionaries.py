
from fastapi import APIRouter, status

from app.api.deps import PageNo, PageSize
from app.core.permissions import DbSession, SuperAdmin
from app.schemas import (
    Page,
    UserApiTokenRead,
    UserApiTokenRegenerate,
    UserCreate,
    UserUpdate,
)
from app.services import dictionary_service

router = APIRouter(tags=["基础数据"])


@router.get("/users", response_model=Page[UserApiTokenRead])
async def users(
    session: DbSession,
    user: SuperAdmin,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: str | None = None,
) -> Page[UserApiTokenRead]:
    items, total = await dictionary_service.list_users(session, keyword, page, page_size)
    return Page(
        items=[UserApiTokenRead.model_validate(x) for x in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/users", response_model=UserApiTokenRead, status_code=status.HTTP_201_CREATED)
async def add_user(
    data: UserCreate, session: DbSession, user: SuperAdmin
) -> UserApiTokenRead:
    return UserApiTokenRead.model_validate(await dictionary_service.create_user(session, data))


@router.patch("/users/{item_id}", response_model=UserApiTokenRead)
async def edit_user(
    item_id: int, data: UserUpdate, session: DbSession, user: SuperAdmin
) -> UserApiTokenRead:
    return UserApiTokenRead.model_validate(
        await dictionary_service.update_user(session, item_id, data)
    )


@router.post("/users/{item_id}/api-token/regenerate", response_model=UserApiTokenRead)
async def regenerate_user_api_token(
    item_id: int,
    data: UserApiTokenRegenerate,
    session: DbSession,
    user: SuperAdmin,
) -> UserApiTokenRead:
    return UserApiTokenRead.model_validate(
        await dictionary_service.regenerate_user_api_token(session, item_id, data.version)
    )


@router.delete("/users/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(item_id: int, session: DbSession, user: SuperAdmin) -> None:
    await dictionary_service.delete_user(session, item_id, user.id)
