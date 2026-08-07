from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app.api.deps import PageNo, PageSize
from app.core.permissions import (
    CurrentMiniProgramUser,
    DbSession,
    IfMatchVersion,
    MiniProgramRegistrationOpenId,
    SuperAdmin,
)
from app.core.security import (
    create_mini_program_access_token,
    create_mini_program_registration_token,
)
from app.domain.enums import MiniProgramStockStatus
from app.schemas import (
    MiniProgramInventoryItemRead,
    MiniProgramLoginResponse,
    MiniProgramMaterialRead,
    MiniProgramOperationRead,
    MiniProgramOutboundCreate,
    MiniProgramOutboundRead,
    MiniProgramOutboundReasonOptions,
    MiniProgramProfileUpdate,
    MiniProgramPurchasePlanDetailRead,
    MiniProgramPurchasePlanItemRead,
    MiniProgramUserMergeRequest,
    MiniProgramUserRead,
    MiniProgramUserUpdate,
    MiniProgramWechatLoginRequest,
    Page,
)
from app.services import mini_program_service

management_router = APIRouter(prefix="/mini-program-users", tags=["小程序用户管理"])
mini_router = APIRouter(prefix="/mini-program", tags=["小程序"])
AcceptLanguage = Annotated[str | None, Header(alias="Accept-Language")]


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


@management_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mini_program_user(
    user_id: int,
    session: DbSession,
    user: SuperAdmin,
    if_match: IfMatchVersion,
) -> None:
    await mini_program_service.delete_user(session, user_id, if_match)


@management_router.post("/{target_user_id}/merge", response_model=MiniProgramUserRead)
async def merge_mini_program_users(
    target_user_id: int,
    data: MiniProgramUserMergeRequest,
    session: DbSession,
    user: SuperAdmin,
) -> MiniProgramUserRead:
    return MiniProgramUserRead.model_validate(
        await mini_program_service.merge_users(session, target_user_id, data)
    )


@mini_router.post("/auth/wx-login", response_model=MiniProgramLoginResponse)
async def mini_program_wechat_login(
    data: MiniProgramWechatLoginRequest, session: DbSession
) -> MiniProgramLoginResponse:
    user, app_id, openid = await mini_program_service.login_with_wechat(
        session, data.code, data.app_id
    )
    if user is None:
        return MiniProgramLoginResponse(
            registration_token=create_mini_program_registration_token(app_id, openid),
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
    identity: MiniProgramRegistrationOpenId,
) -> MiniProgramLoginResponse:
    app_id, openid = identity
    user = await mini_program_service.register_user(
        session, app_id, openid, data.display_name, data.department_name
    )
    return MiniProgramLoginResponse(
        access_token=create_mini_program_access_token(user.id) if user.enabled else None,
        user=MiniProgramUserRead.model_validate(user),
        requires_profile=False,
    )


@mini_router.get("/materials/{material_uuid}", response_model=MiniProgramMaterialRead)
async def scan_material(
    material_uuid: UUID,
    session: DbSession,
    user: CurrentMiniProgramUser,
    accept_language: AcceptLanguage = None,
) -> MiniProgramMaterialRead:
    return mini_program_service.material_read(
        await mini_program_service.get_material(session, material_uuid), accept_language
    )


@mini_router.get("/inventory", response_model=Page[MiniProgramInventoryItemRead])
async def mini_program_inventory(
    session: DbSession,
    user: CurrentMiniProgramUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: Annotated[str | None, Query(max_length=255)] = None,
    stock_status: MiniProgramStockStatus | None = None,
    accept_language: AcceptLanguage = None,
) -> Page[MiniProgramInventoryItemRead]:
    items, total = await mini_program_service.list_inventory(
        session,
        keyword=keyword,
        stock_status=stock_status,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[
            mini_program_service.inventory_item_read(item, accept_language) for item in items
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@mini_router.get("/purchase-plans", response_model=Page[MiniProgramPurchasePlanItemRead])
async def mini_program_purchase_plans(
    session: DbSession,
    user: CurrentMiniProgramUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: Annotated[str | None, Query(max_length=255)] = None,
) -> Page[MiniProgramPurchasePlanItemRead]:
    items, total = await mini_program_service.list_purchase_plans(
        session, keyword, page, page_size
    )
    return Page(
        items=[mini_program_service.purchase_plan_item_read(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@mini_router.get(
    "/purchase-plans/{material_id}", response_model=MiniProgramPurchasePlanDetailRead
)
async def mini_program_purchase_plan_detail(
    material_id: int,
    session: DbSession,
    user: CurrentMiniProgramUser,
) -> MiniProgramPurchasePlanDetailRead:
    return await mini_program_service.purchase_plan_detail(session, material_id)


@mini_router.post(
    "/outbound", response_model=MiniProgramOutboundRead, status_code=status.HTTP_201_CREATED
)
async def mini_program_outbound(
    data: MiniProgramOutboundCreate,
    session: DbSession,
    user: CurrentMiniProgramUser,
) -> MiniProgramOutboundRead:
    return await mini_program_service.create_outbound(session, data, user)


@mini_router.get("/outbound-reasons", response_model=MiniProgramOutboundReasonOptions)
async def mini_program_outbound_reasons(
    session: DbSession,
    user: CurrentMiniProgramUser,
) -> MiniProgramOutboundReasonOptions:
    personal_reasons, system_reasons = await mini_program_service.recent_outbound_reasons(
        session, user
    )
    return MiniProgramOutboundReasonOptions(
        personal_reasons=personal_reasons,
        system_reasons=system_reasons,
    )


@mini_router.get("/operations", response_model=Page[MiniProgramOperationRead])
async def mini_program_operations(
    session: DbSession,
    user: CurrentMiniProgramUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
) -> Page[MiniProgramOperationRead]:
    """按当前用户姓名匹配查询出入库记录（含管理端操作）。"""
    items, total = await mini_program_service.list_operations_by_user(
        session, user, page, page_size
    )
    return Page(items=items, page=page, page_size=page_size, total=total)


@mini_router.get("/outbound/{operation_no}", response_model=MiniProgramOutboundRead)
async def mini_program_outbound_by_no(
    operation_no: str,
    session: DbSession,
    user: CurrentMiniProgramUser,
) -> MiniProgramOutboundRead:
    """按流水号查询小程序出库明细（分享结果页恢复数据用）。"""
    return await mini_program_service.get_outbound_by_no(session, operation_no, user)
