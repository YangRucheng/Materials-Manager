from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from time import monotonic
from typing import cast
from uuid import UUID

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, not_found
from app.core.wechat import get_wechat_credentials
from app.domain.enums import (
    MiniProgramCodeEnv,
    MiniProgramStockStatus,
    OperationType,
    PurchasePlanStatus,
    SourceType,
    WebhookEventType,
)
from app.models import (
    MiniProgramIdentity,
    MiniProgramUser,
    PurchaseMaterial,
    PurchaseRequestLine,
    StockBalance,
    StockMaterial,
    StockOperation,
    StockReplenishmentPolicy,
)
from app.repositories import purchase_request_repository
from app.schemas import (
    MiniProgramHuaXingInventoryRead,
    MiniProgramInventoryItemRead,
    MiniProgramLiteInventoryItemRead,
    MiniProgramMaterialCodeRead,
    MiniProgramMaterialRead,
    MiniProgramOperationRead,
    MiniProgramOutboundCreate,
    MiniProgramOutboundRead,
    MiniProgramOutboundReason,
    MiniProgramPurchasePlanDetailRead,
    MiniProgramPurchasePlanItemRead,
    MiniProgramPurchaseRecordItemRead,
    MiniProgramUserMergeRequest,
    MiniProgramUserUpdate,
    OperationCreate,
    OperationLineWrite,
)
from app.services import (
    ai_search_service,
    huaxing_inventory_service,
    inventory_service,
    lite_inventory_service,
    material_code_library_service,
    webhook_service,
)
from app.services.common import contains_any, file_read, utc_aware, validate_version

_wechat_access_tokens: dict[str, tuple[str, float]] = {}
_wechat_access_token_lock = asyncio.Lock()
_material_code_cache: dict[tuple[str, MiniProgramCodeEnv, str], bytes] = {}
_material_code_lock = asyncio.Lock()


async def list_users(
    session: AsyncSession, keyword: str | None, page: int, page_size: int
) -> tuple[list[MiniProgramUser], int]:
    query = select(MiniProgramUser).options(selectinload(MiniProgramUser.identities))
    if keyword:
        query = query.where(
            or_(
                MiniProgramUser.display_name.contains(keyword, autoescape=True),
                MiniProgramUser.department_name.contains(keyword, autoescape=True),
                MiniProgramUser.identities.any(
                    or_(
                        MiniProgramIdentity.app_id.contains(keyword, autoescape=True),
                        MiniProgramIdentity.wechat_openid.contains(keyword, autoescape=True),
                    )
                ),
            )
        )
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    items = list(
        (
            await session.scalars(
                query.order_by(MiniProgramUser.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, total


async def list_purchase_plans(
    session: AsyncSession,
    keyword: str | None,
    page: int,
    page_size: int,
    actual_demand_person: str | None = None,
    subitem_no: str | None = None,
) -> tuple[list[PurchaseMaterial], int]:
    query = select(PurchaseMaterial).where(
        PurchaseMaterial.status == PurchasePlanStatus.NORMAL,
        ~(
            select(PurchaseRequestLine.id)
            .where(PurchaseRequestLine.purchase_material_id == PurchaseMaterial.id)
            .exists()
        ),
    )
    keyword_condition = contains_any(
        (PurchaseMaterial.name, PurchaseMaterial.model_spec),
        keyword,
    )
    if keyword_condition is not None:
        query = query.where(keyword_condition)
    if actual_demand_person:
        person_condition = contains_any(
            (PurchaseMaterial.actual_demand_person,), actual_demand_person
        )
        if person_condition is not None:
            query = query.where(person_condition)
    if subitem_no:
        query = query.where(func.trim(PurchaseMaterial.subitem_no) == subitem_no.strip())
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    items = list(
        (
            await session.scalars(
                query.order_by(PurchaseMaterial.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, total


async def list_purchase_plan_filter_options(
    session: AsyncSession,
) -> tuple[list[str], list[str]]:
    record_exists = (
        select(PurchaseRequestLine.id)
        .where(PurchaseRequestLine.purchase_material_id == PurchaseMaterial.id)
        .exists()
    )
    active = ~record_exists
    actual_demand_query = select(PurchaseMaterial.actual_demand_person).where(
        PurchaseMaterial.status == PurchasePlanStatus.NORMAL,
        active,
        func.trim(PurchaseMaterial.actual_demand_person) != "",
    )
    subitem_query = select(PurchaseMaterial.subitem_no).where(
        PurchaseMaterial.status == PurchasePlanStatus.NORMAL,
        active,
        PurchaseMaterial.subitem_no.is_not(None),
        func.trim(PurchaseMaterial.subitem_no) != "",
    )
    actual_demand_persons = list(
        await session.scalars(
            actual_demand_query.distinct().order_by(PurchaseMaterial.actual_demand_person)
        )
    )
    subitem_nos = [
        value
        for value in await session.scalars(
            subitem_query.distinct().order_by(PurchaseMaterial.subitem_no)
        )
        if value is not None
    ]
    return actual_demand_persons, subitem_nos


def purchase_plan_item_read(item: PurchaseMaterial) -> MiniProgramPurchasePlanItemRead:
    return MiniProgramPurchasePlanItemRead.model_validate(item)


async def list_purchase_records(
    session: AsyncSession,
    *,
    keyword: str | None = None,
    status: str | None = None,
    subitem_no: str | None = None,
    page: int = 1,
    page_size: int = 15,
) -> tuple[list[PurchaseRequestLine], int]:
    return await purchase_request_repository.search_mini_program_purchase_records(
        session,
        keyword=keyword,
        status=status,
        subitem_no=subitem_no,
        page=page,
        page_size=page_size,
    )


async def list_purchase_record_filter_options(
    session: AsyncSession,
) -> tuple[list[str], list[str]]:
    statuses = await purchase_request_repository.purchase_status_options(session)
    subitem_nos = await purchase_request_repository.purchase_subitem_options(session)
    return statuses, subitem_nos


async def list_material_codes(
    session: AsyncSession, *, keyword: str | None, page: int, page_size: int
) -> tuple[list[MiniProgramMaterialCodeRead], int]:
    items, total = await material_code_library_service.search_material_codes(
        session, keyword=keyword, page=page, page_size=page_size
    )
    return (
        [
            MiniProgramMaterialCodeRead(
                id=item.id,
                material_code=item.material_code,
                name=item.name,
                model_spec=item.model_spec,
                unit_name=item.unit_name,
            )
            for item in items
        ],
        total,
    )


async def list_huaxing_inventory(
    session: AsyncSession, *, keyword: str | None, page: int, page_size: int
) -> tuple[list[MiniProgramHuaXingInventoryRead], int]:
    items, total = await huaxing_inventory_service.search_huaxing_inventory(
        session,
        keyword=keyword,
        purchase_department=None,
        purchaser=None,
        page=page,
        page_size=page_size,
    )
    return (
        [
            MiniProgramHuaXingInventoryRead(
                id=item.id,
                first_inbound_date=item.first_inbound_date,
                warehouse=item.warehouse,
                material_code=item.material_code,
                name=item.name,
                model_spec=item.model_spec,
                quantity=item.quantity,
                unit_name=item.unit_name,
                purchaser=item.purchaser,
                purchase_department=item.purchase_department,
                subitem_no_name=item.subitem_no_name,
            )
            for item in items
        ],
        total,
    )


async def list_lite_inventory(
    session: AsyncSession, *, keyword: str | None, page: int, page_size: int
) -> tuple[list[MiniProgramLiteInventoryItemRead], int]:
    """精简二级库列表（仅查看，无出入库）。"""
    items, total = await lite_inventory_service.search_lite_inventory(
        session, keyword=keyword, page=page, page_size=page_size
    )
    return (
        [
            MiniProgramLiteInventoryItemRead(
                id=item.id,
                name=item.name,
                model_spec=item.model_spec,
                unit_name=item.unit_name,
                quantity=item.quantity,
            )
            for item in items
        ],
        total,
    )


def purchase_record_item_read(line: PurchaseRequestLine) -> MiniProgramPurchaseRecordItemRead:
    request = line.request
    return MiniProgramPurchaseRecordItemRead(
        line_id=line.id,
        material_name=line.material_name_snapshot,
        model_spec=line.model_spec_snapshot,
        purchase_order_no=request.purchase_order_no,
        trace_no=line.trace_no,
        status=line.status,
        unit_name=line.unit_name_snapshot,
        purchase_qty=line.purchase_qty,
        plan_date=line.plan_date_snapshot,
        subitem_no=line.subitem_no,
        material_code=line.material_code_snapshot,
        category=line.category_snapshot,
        plan_no=line.plan_no_snapshot,
        demand_department=line.demand_department_snapshot,
        actual_demand_person=line.actual_demand_person_snapshot,
        purchase_responsible=line.purchase_responsible_snapshot,
        usage=line.usage,
        remark=request.remark,
        purchase_date=request.purchase_date,
        salesperson=line.salesperson,
        images=[file_read(link.file) for link in line.images],
    )


async def purchase_plan_detail(
    session: AsyncSession, material_id: int
) -> MiniProgramPurchasePlanDetailRead:
    item = await session.scalar(
        select(PurchaseMaterial).where(
            PurchaseMaterial.id == material_id,
            PurchaseMaterial.status == PurchasePlanStatus.NORMAL,
            ~(
                select(PurchaseRequestLine.id)
                .where(PurchaseRequestLine.purchase_material_id == PurchaseMaterial.id)
                .exists()
            ),
        )
    )
    if item is None:
        raise not_found("申购计划")
    next_id = await session.scalar(
        select(PurchaseMaterial.id)
        .where(
            PurchaseMaterial.status == PurchasePlanStatus.NORMAL,
            PurchaseMaterial.id < item.id,
            ~(
                select(PurchaseRequestLine.id)
                .where(PurchaseRequestLine.purchase_material_id == PurchaseMaterial.id)
                .exists()
            ),
        )
        .order_by(PurchaseMaterial.id.desc())
        .limit(1)
    )
    return MiniProgramPurchasePlanDetailRead(
        **MiniProgramPurchasePlanItemRead.model_validate(item).model_dump(),
        material_code=item.material_code,
        category=item.category,
        demand_department=item.demand_department,
        usage=item.usage,
        subitem_no=item.subitem_no,
        remark=item.remark,
        images=[file_read(link.file) for link in item.images],
        next_id=next_id,
    )


async def update_user(
    session: AsyncSession, item_id: int, data: MiniProgramUserUpdate
) -> MiniProgramUser:
    item = await session.get(MiniProgramUser, item_id)
    if item is None:
        raise not_found("小程序用户")
    validate_version(data.version, item.version)
    if data.display_name is not None:
        item.display_name = data.display_name
    if data.department_name is not None:
        item.department_name = data.department_name
    if data.enabled is not None:
        item.enabled = data.enabled
    item.version += 1
    await session.flush()
    return item


async def delete_user(session: AsyncSession, item_id: int, version: int | None) -> None:
    item = await session.get(MiniProgramUser, item_id)
    if item is None:
        raise not_found("小程序用户")
    validate_version(version, item.version)
    await session.delete(item)
    await session.flush()


async def merge_users(
    session: AsyncSession,
    target_user_id: int,
    data: MiniProgramUserMergeRequest,
) -> MiniProgramUser:
    if target_user_id == data.source_user_id:
        raise AppError(
            "MINI_PROGRAM_USER_MERGE_SAME_ACCOUNT",
            "不能将小程序账号合并到自身",
            status_code=400,
        )
    users = list(
        (
            await session.scalars(
                select(MiniProgramUser)
                .where(MiniProgramUser.id.in_([target_user_id, data.source_user_id]))
                .options(selectinload(MiniProgramUser.identities))
                .with_for_update()
            )
        ).all()
    )
    by_id = {item.id: item for item in users}
    target = by_id.get(target_user_id)
    source = by_id.get(data.source_user_id)
    if target is None or source is None:
        raise not_found("小程序用户")
    validate_version(data.target_version, target.version)
    validate_version(data.source_version, source.version)

    if (
        target.display_name != source.display_name
        or target.department_name != source.department_name
    ):
        raise AppError(
            "MINI_PROGRAM_USER_PROFILE_MISMATCH",
            "姓名和部门单位必须一致才能合并账号",
            status_code=409,
        )

    target_app_ids = {identity.app_id for identity in target.identities}
    duplicate_app_ids = sorted(
        target_app_ids.intersection(identity.app_id for identity in source.identities)
    )
    if duplicate_app_ids:
        raise AppError(
            "MINI_PROGRAM_IDENTITY_CONFLICT",
            "两个账号包含相同小程序的身份，无法直接合并",
            status_code=409,
            details={"app_ids": duplicate_app_ids},
        )

    for identity in list(source.identities):
        source.identities.remove(identity)
        target.identities.append(identity)
    target.version += 1
    await session.delete(source)
    await session.flush()
    return target


async def exchange_wechat_code(code: str, app_id: str | None = None) -> tuple[str, str]:
    effective_app_id, app_secret = get_wechat_credentials(app_id)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": effective_app_id,
                    "secret": app_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AppError(
            "WECHAT_AUTH_UNAVAILABLE",
            "微信登录服务暂时不可用，请稍后重试",
            status_code=503,
        ) from exc
    if payload.get("errcode"):
        raise AppError(
            "WECHAT_AUTH_FAILED",
            "微信登录凭证无效，请重试",
            status_code=401,
            details={"wechat_errcode": payload.get("errcode")},
        )
    openid = payload.get("openid")
    if not isinstance(openid, str) or not openid:
        raise AppError(
            "WECHAT_AUTH_INVALID_RESPONSE",
            "微信登录服务返回异常",
            status_code=502,
        )
    return effective_app_id, openid


async def _get_wechat_access_token(app_id: str) -> str:
    app_id, app_secret = get_wechat_credentials(app_id)
    cached = _wechat_access_tokens.get(app_id)
    if cached and monotonic() < cached[1]:
        return cached[0]

    async with _wechat_access_token_lock:
        cached = _wechat_access_tokens.get(app_id)
        if cached and monotonic() < cached[1]:
            return cached[0]
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    "https://api.weixin.qq.com/cgi-bin/token",
                    params={
                        "grant_type": "client_credential",
                        "appid": app_id,
                        "secret": app_secret,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError(
                "WECHAT_ACCESS_TOKEN_UNAVAILABLE",
                "微信接口调用暂时不可用，请稍后重试",
                status_code=503,
            ) from exc
        token = payload.get("access_token")
        if payload.get("errcode") or not isinstance(token, str) or not token:
            raise AppError(
                "WECHAT_ACCESS_TOKEN_FAILED",
                "微信接口凭证获取失败",
                status_code=502,
                details={"wechat_errcode": payload.get("errcode")},
            )
        expires_in = payload.get("expires_in", 7200)
        _wechat_access_tokens[app_id] = (
            token,
            monotonic() + max(int(expires_in) - 300, 60),
        )
        return token


async def generate_unlimited_material_code(
    material_uuid: UUID, env: MiniProgramCodeEnv, app_id: str
) -> bytes:
    cache_key = (str(material_uuid), env, app_id)
    cached = _material_code_cache.get(cache_key)
    if cached is not None:
        return cached

    async with _material_code_lock:
        cached = _material_code_cache.get(cache_key)
        if cached is not None:
            return cached
        access_token = await _get_wechat_access_token(app_id)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://api.weixin.qq.com/wxa/getwxacodeunlimit",
                    params={"access_token": access_token},
                    json={
                        "scene": material_uuid.hex,
                        "page": "pages/outbound/outbound",
                        "check_path": False,
                        "env_version": env,
                        "width": 430,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                "WECHAT_MINI_PROGRAM_CODE_UNAVAILABLE",
                "小程序码生成服务暂时不可用，请稍后重试",
                status_code=503,
            ) from exc
        if response.headers.get("content-type", "").startswith("image/"):
            _material_code_cache[cache_key] = response.content
            return response.content
        try:
            payload = response.json()
        except ValueError as exc:
            raise AppError(
                "WECHAT_MINI_PROGRAM_CODE_INVALID_RESPONSE",
                "小程序码生成服务返回异常",
                status_code=502,
            ) from exc
        raise AppError(
            "WECHAT_MINI_PROGRAM_CODE_FAILED",
            "小程序码生成失败",
            status_code=502,
            details={"wechat_errcode": payload.get("errcode")},
        )


async def login_with_wechat(
    session: AsyncSession, code: str, app_id: str | None = None
) -> tuple[MiniProgramUser | None, str, str]:
    effective_app_id, openid = await exchange_wechat_code(code, app_id)
    user = await session.scalar(
        select(MiniProgramUser)
        .join(MiniProgramIdentity)
        .where(
            MiniProgramIdentity.app_id == effective_app_id,
            MiniProgramIdentity.wechat_openid == openid,
        )
        .options(selectinload(MiniProgramUser.identities))
    )
    if user is not None and not user.enabled:
        raise AppError("ACCOUNT_DISABLED", "您的账号待审核，请联系管理员", status_code=403)
    if user is None and not await ai_search_service.is_mini_program_registration_enabled(session):
        raise AppError(
            "MINI_PROGRAM_REGISTRATION_DISABLED",
            "当前暂未开放新用户绑定，请联系管理员",
            status_code=403,
        )
    return user, effective_app_id, openid


async def register_user(
    session: AsyncSession,
    app_id: str,
    openid: str,
    display_name: str,
    department_name: str,
) -> MiniProgramUser:
    existing = await session.scalar(
        select(MiniProgramUser)
        .join(MiniProgramIdentity)
        .where(
            MiniProgramIdentity.app_id == app_id,
            MiniProgramIdentity.wechat_openid == openid,
        )
        .options(selectinload(MiniProgramUser.identities))
    )
    if existing is not None:
        if not existing.enabled:
            raise AppError("ACCOUNT_DISABLED", "您的账号待审核，请联系管理员", status_code=403)
        return existing
    if not await ai_search_service.is_mini_program_registration_enabled(session):
        raise AppError(
            "MINI_PROGRAM_REGISTRATION_DISABLED",
            "当前暂未开放新用户绑定，请联系管理员",
            status_code=403,
        )
    user = MiniProgramUser(
        display_name=display_name,
        department_name=department_name,
        enabled=await ai_search_service.is_mini_program_new_user_enabled(session),
        identities=[MiniProgramIdentity(app_id=app_id, wechat_openid=openid)],
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(
            "WECHAT_USER_CREATE_CONFLICT",
            "微信用户创建冲突，请重新登录",
            status_code=409,
        ) from exc
    await webhook_service.enqueue_event(
        session,
        WebhookEventType.MINI_PROGRAM_USER_BOUND,
        {
            "display_name": user.display_name,
            "department_name": user.department_name,
            "app_id": app_id,
            "enabled": user.enabled,
            "bound_at": user.created_at.isoformat(timespec="seconds") + "Z",
        },
    )
    return user


async def get_material(
    session: AsyncSession, material_uuid: UUID, *, for_update: bool = False
) -> StockMaterial:
    query = select(StockMaterial).where(StockMaterial.uuid == str(material_uuid))
    if for_update:
        query = query.with_for_update()
    item = await session.scalar(query)
    if item is None:
        raise not_found("二级库物资")
    return item


def _stock_status(item: StockMaterial) -> MiniProgramStockStatus:
    current_qty = item.balance.quantity if item.balance else Decimal("0")
    if current_qty <= 0:
        return MiniProgramStockStatus.OUT_OF_STOCK
    policy = item.replenishment_policy
    if policy is not None and policy.enabled and current_qty <= policy.minimum_qty:
        return MiniProgramStockStatus.LOW_STOCK
    return MiniProgramStockStatus.NORMAL


async def list_inventory(
    session: AsyncSession,
    *,
    keyword: str | None,
    stock_status: MiniProgramStockStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[StockMaterial], int]:
    current_qty = func.coalesce(StockBalance.quantity, Decimal("0"))
    query = (
        select(StockMaterial)
        .outerjoin(StockBalance, StockBalance.stock_material_id == StockMaterial.id)
        .outerjoin(
            StockReplenishmentPolicy,
            StockReplenishmentPolicy.stock_material_id == StockMaterial.id,
        )
    )
    keyword_condition = contains_any(
        (StockMaterial.name, StockMaterial.name_id, StockMaterial.alias, StockMaterial.model_spec),
        keyword,
    )
    if keyword_condition is not None:
        query = query.where(keyword_condition)
    if stock_status == MiniProgramStockStatus.OUT_OF_STOCK:
        query = query.where(current_qty <= 0)
    elif stock_status == MiniProgramStockStatus.LOW_STOCK:
        query = query.where(
            current_qty > 0,
            StockReplenishmentPolicy.enabled.is_(True),
            current_qty <= StockReplenishmentPolicy.minimum_qty,
        )
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    items = list(
        (
            await session.scalars(
                query.order_by(StockMaterial.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return items, total


def localized_material_name(item: StockMaterial, language: str | None) -> str:
    """Localize the name; aliases are shown only with the canonical Chinese name."""
    preferred = (language or "").split(",", maxsplit=1)[0].split(";", maxsplit=1)[0]
    language_code = preferred.strip().replace("_", "-").lower().split("-", maxsplit=1)[0]
    if language_code in {"id", "in"}:
        return item.name_id or item.name
    return f"{item.name}（{item.alias}）" if item.alias else item.name


def inventory_item_read(
    item: StockMaterial, language: str | None = None
) -> MiniProgramInventoryItemRead:
    return MiniProgramInventoryItemRead(
        uuid=UUID(item.uuid),
        name=localized_material_name(item, language),
        model_spec=item.model_spec,
        unit_name=item.unit_name,
        current_qty=item.balance.quantity if item.balance else Decimal("0"),
        stock_status=_stock_status(item),
    )


def material_read(item: StockMaterial, language: str | None = None) -> MiniProgramMaterialRead:
    policy = item.replenishment_policy
    return MiniProgramMaterialRead(
        uuid=UUID(item.uuid),
        name=localized_material_name(item, language),
        model_spec=item.model_spec,
        unit_name=item.unit_name,
        current_qty=item.balance.quantity if item.balance else Decimal("0"),
        stock_status=_stock_status(item),
        minimum_qty=policy.minimum_qty if policy is not None and policy.enabled else None,
        remark=item.remark,
        images=[file_read(link.file) for link in item.images],
    )


def _outbound_read(
    item: StockOperation, material: StockMaterial, user: MiniProgramUser
) -> MiniProgramOutboundRead:
    if (
        item.operation_type != OperationType.OUTBOUND
        or len(item.lines) != 1
        or item.lines[0].stock_material_id != material.id
    ):
        raise AppError(
            "CLIENT_REQUEST_ID_CONFLICT",
            "请求标识已被其他出库业务使用",
            status_code=409,
        )
    line = item.lines[0]
    return MiniProgramOutboundRead(
        operation_id=item.id,
        operation_no=item.operation_no,
        material_uuid=UUID(material.uuid),
        material_name=line.material_name_snapshot,
        model_spec=line.model_spec_snapshot,
        unit_name=line.unit_name_snapshot,
        quantity=line.quantity,
        before_qty=line.before_qty,
        after_qty=line.after_qty,
        occurred_at=cast(datetime, utc_aware(item.occurred_at)),
        business_reason=item.business_reason,
        receiver_unit=item.receiver_unit,
        receiver_name=item.receiver_name or "",
        subitem_no=item.subitem_no,
        executed_by=item.mini_program_user_name_snapshot or user.display_name,
    )


async def _ensure_not_lite_secondary_warehouse(session: AsyncSession) -> None:
    """精简模式下二级库仅支持查看，拦截小程序出入库相关调用。"""
    if await ai_search_service.is_lite_secondary_warehouse(session):
        raise AppError(
            "OUTBOUND_DISABLED",
            "二级库精简模式下不支持出入库",
            status_code=403,
        )


async def recent_outbound_reasons(
    session: AsyncSession, user: MiniProgramUser
) -> tuple[list[MiniProgramOutboundReason], list[MiniProgramOutboundReason]]:
    await _ensure_not_lite_secondary_warehouse(session)

    async def list_reasons(user_name: str | None = None) -> list[MiniProgramOutboundReason]:
        last_used_at = func.max(StockOperation.occurred_at)
        last_operation_id = func.max(StockOperation.id)
        query = (
            select(StockOperation.subitem_no, StockOperation.business_reason)
            .where(
                StockOperation.operation_type == OperationType.OUTBOUND,
                StockOperation.business_reason != "",
            )
            .group_by(StockOperation.subitem_no, StockOperation.business_reason)
            .order_by(last_used_at.desc(), last_operation_id.desc())
            .limit(3)
        )
        if user_name is not None:
            query = query.where(StockOperation.mini_program_user_name_snapshot == user_name)
        rows = (await session.execute(query)).all()
        return [
            MiniProgramOutboundReason(subitem_no=subitem_no, reason=reason)
            for subitem_no, reason in rows
        ]

    personal_reasons = await list_reasons(user.display_name)
    system_reasons = await list_reasons()
    return personal_reasons, system_reasons


async def create_outbound(
    session: AsyncSession, data: MiniProgramOutboundCreate, user: MiniProgramUser
) -> MiniProgramOutboundRead:
    await _ensure_not_lite_secondary_warehouse(session)
    material = await get_material(session, data.material_uuid, for_update=True)
    operation = await inventory_service.create_operation(
        session,
        OperationCreate(
            client_request_id=data.client_request_id,
            occurred_at=data.occurred_at,
            source_type=SourceType.MINI_PROGRAM,
            business_reason=data.business_reason,
            receiver_unit=data.receiver_unit or None,
            receiver_name=user.display_name,
            subitem_no=data.subitem_no,
            lines=[OperationLineWrite(stock_material_id=material.id, quantity=data.quantity)],
        ),
        OperationType.OUTBOUND,
        mini_program_user=user,
    )
    return _outbound_read(operation, material, user)


async def get_outbound_by_no(
    session: AsyncSession, operation_no: str, user: MiniProgramUser
) -> MiniProgramOutboundRead:
    """按流水号查询小程序出库明细，供分享结果页恢复数据使用。

    仅接受小程序扫码的出库流水：小程序来源的流水在数据库中 source_type 存为 MANUAL，
    但 mini_program_user_name_snapshot 非空（见 inventory_service.create_operation）。
    用它作为真实来源判别，避免通过流水号枚举其他渠道的库存操作。
    """
    operation = await session.scalar(
        select(StockOperation).where(
            StockOperation.operation_no == operation_no,
            StockOperation.operation_type == OperationType.OUTBOUND,
            StockOperation.mini_program_user_name_snapshot.is_not(None),
        )
    )
    if operation is None or len(operation.lines) != 1:
        raise not_found("出库流水")
    material = await session.scalar(
        select(StockMaterial).where(StockMaterial.id == operation.lines[0].stock_material_id)
    )
    if material is None:
        raise not_found("二级库物资")
    return _outbound_read(operation, material, user)


def operation_read_rows(item: StockOperation) -> list[MiniProgramOperationRead]:
    """把一条库存操作按行展平为小程序出入库记录（兼容入库/出库、多行/管理端操作）。

    仅使用各行的快照字段，不依赖实时关联，历史数据稳定。
    """
    executed_by = item.mini_program_user_name_snapshot or item.receiver_name
    rows: list[MiniProgramOperationRead] = []
    for line in item.lines:
        rows.append(
            MiniProgramOperationRead(
                operation_id=item.id,
                operation_no=item.operation_no,
                operation_type=item.operation_type,
                material_name=line.material_name_snapshot,
                model_spec=line.model_spec_snapshot,
                unit_name=line.unit_name_snapshot,
                quantity=line.quantity,
                before_qty=line.before_qty,
                after_qty=line.after_qty,
                occurred_at=cast(datetime, utc_aware(item.occurred_at)),
                business_reason=item.business_reason,
                receiver_unit=item.receiver_unit,
                receiver_name=item.receiver_name,
                subitem_no=item.subitem_no,
                executed_by=executed_by,
            )
        )
    return rows


async def list_operations_by_user(
    session: AsyncSession, user: MiniProgramUser, page: int, page_size: int
) -> tuple[list[MiniProgramOperationRead], int]:
    """按当前用户姓名匹配查询所有出入库记录（含管理端操作）。

    姓名匹配 receiver_name（领用人）或 mini_program_user_name_snapshot（小程序执行人）。
    服务端用 user.display_name 匹配，不接受客户端传姓名，避免越权查看他人记录。
    空结果返回空列表，不抛 404（符合禁止 404 约定）。
    """
    condition = or_(
        StockOperation.receiver_name == user.display_name,
        StockOperation.mini_program_user_name_snapshot == user.display_name,
    )
    total = int(
        (
            await session.scalar(
                select(func.count()).select_from(StockOperation).where(condition)
            )
        )
        or 0
    )
    items = list(
        (
            await session.scalars(
                select(StockOperation)
                .where(condition)
                .order_by(StockOperation.occurred_at.desc(), StockOperation.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return [row for item in items for row in operation_read_rows(item)], total
