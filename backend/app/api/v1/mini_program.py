from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.permissions import (
    CurrentMiniProgramUser,
    DbSession,
    MiniProgramRegistrationOpenId,
    SuperAdmin,
)
from app.core.security import (
    create_mini_program_access_token,
    create_mini_program_registration_token,
)
from app.schemas import (
    MiniProgramLoginResponse,
    MiniProgramMaterialRead,
    MiniProgramOutboundCreate,
    MiniProgramOutboundRead,
    MiniProgramProfileUpdate,
    MiniProgramUserRead,
    MiniProgramUserUpdate,
    MiniProgramWechatLoginRequest,
    Page,
)
from app.services import mini_program_service

management_router = APIRouter(prefix="/mini-program-users", tags=["小程序用户管理"])
mini_router = APIRouter(prefix="/mini-program", tags=["小程序扫码出库"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]


@management_router.get("", response_model=Page[MiniProgramUserRead])
async def list_mini_program_users(
    session: DbSession,
    user: SuperAdmin,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: Annotated[str | None, Query(max_length=128)] = None,
) -> Page[MiniProgramUserRead]:
    items, total = await mini_program_service.list_users(session, keyword, page, page_size)
    return Page(
        items=[MiniProgramUserRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@management_router.patch("/{user_id}", response_model=MiniProgramUserRead)
async def update_mini_program_user(
    user_id: int,
    data: MiniProgramUserUpdate,
    session: DbSession,
    user: SuperAdmin,
) -> MiniProgramUserRead:
    return MiniProgramUserRead.model_validate(
        await mini_program_service.update_user(session, user_id, data)
    )


@mini_router.post("/auth/wx-login", response_model=MiniProgramLoginResponse)
async def mini_program_wechat_login(
    data: MiniProgramWechatLoginRequest, session: DbSession
) -> MiniProgramLoginResponse:
    user, openid = await mini_program_service.login_with_wechat(session, data.code)
    if user is None:
        return MiniProgramLoginResponse(
            registration_token=create_mini_program_registration_token(openid),
            requires_profile=True,
        )
    return MiniProgramLoginResponse(
        access_token=create_mini_program_access_token(user.id),
        user=MiniProgramUserRead.model_validate(user),
        requires_profile=False,
    )


@mini_router.get("/me", response_model=MiniProgramUserRead)
async def mini_program_me(user: CurrentMiniProgramUser) -> MiniProgramUserRead:
    return MiniProgramUserRead.model_validate(user)


@mini_router.post("/profile", response_model=MiniProgramLoginResponse)
async def create_mini_program_profile(
    data: MiniProgramProfileUpdate,
    session: DbSession,
    openid: MiniProgramRegistrationOpenId,
) -> MiniProgramLoginResponse:
    user = await mini_program_service.register_user(session, openid, data.display_name)
    return MiniProgramLoginResponse(
        access_token=create_mini_program_access_token(user.id),
        user=MiniProgramUserRead.model_validate(user),
        requires_profile=False,
    )


@mini_router.get("/materials/{material_uuid}", response_model=MiniProgramMaterialRead)
async def scan_material(
    material_uuid: UUID, session: DbSession, user: CurrentMiniProgramUser
) -> MiniProgramMaterialRead:
    return mini_program_service.material_read(
        await mini_program_service.get_material(session, material_uuid)
    )


@mini_router.post(
    "/outbound", response_model=MiniProgramOutboundRead, status_code=status.HTTP_201_CREATED
)
async def mini_program_outbound(
    data: MiniProgramOutboundCreate,
    session: DbSession,
    user: CurrentMiniProgramUser,
) -> MiniProgramOutboundRead:
    return await mini_program_service.create_outbound(session, data, user)
