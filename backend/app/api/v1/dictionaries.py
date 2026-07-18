from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.permissions import CurrentUser, DbSession, SuperAdmin
from app.schemas import (
    MeasurementUnitCreate,
    MeasurementUnitRead,
    MeasurementUnitUpdate,
    Page,
    ProjectSubitemCreate,
    ProjectSubitemRead,
    ProjectSubitemUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.services import dictionary_service

router = APIRouter(tags=["基础数据"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]


@router.get("/measurement-units", response_model=Page[MeasurementUnitRead])
async def units(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: str | None = None,
    enabled: bool | None = None,
) -> Page[MeasurementUnitRead]:
    items, total = await dictionary_service.list_units(session, keyword, enabled, page, page_size)
    return Page(
        items=[MeasurementUnitRead.model_validate(x) for x in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/measurement-units", response_model=MeasurementUnitRead, status_code=status.HTTP_201_CREATED
)
async def add_unit(
    data: MeasurementUnitCreate, session: DbSession, user: SuperAdmin
) -> MeasurementUnitRead:
    return MeasurementUnitRead.model_validate(
        await dictionary_service.create_unit(session, data, user.id)
    )


@router.patch("/measurement-units/{item_id}", response_model=MeasurementUnitRead)
async def edit_unit(
    item_id: int, data: MeasurementUnitUpdate, session: DbSession, user: SuperAdmin
) -> MeasurementUnitRead:
    return MeasurementUnitRead.model_validate(
        await dictionary_service.update_unit(session, item_id, data, user.id)
    )


@router.get("/project-subitems", response_model=Page[ProjectSubitemRead])
async def projects(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: str | None = None,
    enabled: bool | None = None,
) -> Page[ProjectSubitemRead]:
    items, total = await dictionary_service.list_projects(
        session, keyword, enabled, page, page_size
    )
    return Page(
        items=[ProjectSubitemRead.model_validate(x) for x in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/project-subitems", response_model=ProjectSubitemRead, status_code=status.HTTP_201_CREATED
)
async def add_project(
    data: ProjectSubitemCreate, session: DbSession, user: SuperAdmin
) -> ProjectSubitemRead:
    return ProjectSubitemRead.model_validate(
        await dictionary_service.create_project(session, data, user.id)
    )


@router.patch("/project-subitems/{item_id}", response_model=ProjectSubitemRead)
async def edit_project(
    item_id: int, data: ProjectSubitemUpdate, session: DbSession, user: SuperAdmin
) -> ProjectSubitemRead:
    return ProjectSubitemRead.model_validate(
        await dictionary_service.update_project(session, item_id, data, user.id)
    )


@router.get("/users", response_model=Page[UserRead])
async def users(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: str | None = None,
) -> Page[UserRead]:
    items, total = await dictionary_service.list_users(session, keyword, page, page_size)
    return Page(
        items=[UserRead.model_validate(x) for x in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def add_user(data: UserCreate, session: DbSession, user: SuperAdmin) -> UserRead:
    return UserRead.model_validate(await dictionary_service.create_user(session, data))


@router.patch("/users/{item_id}", response_model=UserRead)
async def edit_user(
    item_id: int, data: UserUpdate, session: DbSession, user: SuperAdmin
) -> UserRead:
    return UserRead.model_validate(await dictionary_service.update_user(session, item_id, data))


@router.delete("/users/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(item_id: int, session: DbSession, user: SuperAdmin) -> None:
    await dictionary_service.delete_user(session, item_id, user.id)
