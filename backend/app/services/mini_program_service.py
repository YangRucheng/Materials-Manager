from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from time import monotonic
from typing import cast
from uuid import UUID

import httpx
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, not_found
from app.domain.enums import (
    MiniProgramCodeEnv,
    MiniProgramStockStatus,
    OperationType,
    SourceType,
)
from app.models import (
    MiniProgramUser,
    StockBalance,
    StockMaterial,
    StockOperation,
    StockReplenishmentPolicy,
)
from app.schemas import (
    MiniProgramInventoryItemRead,
    MiniProgramMaterialRead,
    MiniProgramOutboundCreate,
    MiniProgramOutboundRead,
    MiniProgramUserUpdate,
    OperationCreate,
    OperationLineWrite,
)
from app.services import ai_search_service, inventory_service
from app.services.common import contains_any, file_read, utc_aware, validate_version

_wechat_access_token: str | None = None
_wechat_access_token_expires_at = 0.0
_wechat_access_token_lock = asyncio.Lock()
_material_code_cache: dict[tuple[str, MiniProgramCodeEnv], bytes] = {}
_material_code_lock = asyncio.Lock()


async def list_users(
    session: AsyncSession, keyword: str | None, page: int, page_size: int
) -> tuple[list[MiniProgramUser], int]:
    query = select(MiniProgramUser)
    if keyword:
        query = query.where(
            or_(
                MiniProgramUser.wechat_openid.contains(keyword, autoescape=True),
                MiniProgramUser.display_name.contains(keyword, autoescape=True),
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


async def delete_user(session: AsyncSession, item_id: int, version: int) -> None:
    item = await session.get(MiniProgramUser, item_id)
    if item is None:
        raise not_found("小程序用户")
    validate_version(version, item.version)
    await session.execute(
        update(StockOperation)
        .where(StockOperation.mini_program_user_id == item.id)
        .values(mini_program_user_id=None)
    )
    await session.delete(item)
    await session.flush()


async def exchange_wechat_code(code: str) -> str:
    if not settings.wechat_mini_program_app_id or not settings.wechat_mini_program_app_secret:
        raise AppError(
            "WECHAT_NOT_CONFIGURED",
            "微信小程序登录尚未配置",
            status_code=503,
        )
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": settings.wechat_mini_program_app_id,
                    "secret": settings.wechat_mini_program_app_secret,
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
    return openid


async def _get_wechat_access_token() -> str:
    global _wechat_access_token, _wechat_access_token_expires_at

    if not settings.wechat_mini_program_app_id or not settings.wechat_mini_program_app_secret:
        raise AppError(
            "WECHAT_NOT_CONFIGURED",
            "微信小程序登录尚未配置",
            status_code=503,
        )
    if _wechat_access_token and monotonic() < _wechat_access_token_expires_at:
        return _wechat_access_token

    async with _wechat_access_token_lock:
        if _wechat_access_token and monotonic() < _wechat_access_token_expires_at:
            return _wechat_access_token
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    "https://api.weixin.qq.com/cgi-bin/token",
                    params={
                        "grant_type": "client_credential",
                        "appid": settings.wechat_mini_program_app_id,
                        "secret": settings.wechat_mini_program_app_secret,
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
        _wechat_access_token = token
        _wechat_access_token_expires_at = monotonic() + max(int(expires_in) - 300, 60)
        return token


async def generate_unlimited_material_code(material_uuid: UUID, env: MiniProgramCodeEnv) -> bytes:
    cache_key = (str(material_uuid), env)
    cached = _material_code_cache.get(cache_key)
    if cached is not None:
        return cached

    async with _material_code_lock:
        cached = _material_code_cache.get(cache_key)
        if cached is not None:
            return cached
        access_token = await _get_wechat_access_token()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://api.weixin.qq.com/wxa/getwxacodeunlimit",
                    params={"access_token": access_token},
                    json={
                        "scene": material_uuid.hex,
                        "page": "pages/outbound/index",
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
    session: AsyncSession, code: str
) -> tuple[MiniProgramUser | None, str]:
    openid = await exchange_wechat_code(code)
    user = await session.scalar(
        select(MiniProgramUser).where(MiniProgramUser.wechat_openid == openid)
    )
    if user is not None and not user.enabled:
        raise AppError("ACCOUNT_DISABLED", "您的账号已被禁用", status_code=403)
    if user is None and not await ai_search_service.is_mini_program_registration_enabled(session):
        raise AppError(
            "MINI_PROGRAM_REGISTRATION_DISABLED",
            "当前暂未开放新用户绑定，请联系管理员",
            status_code=403,
        )
    return user, openid


async def register_user(
    session: AsyncSession, openid: str, display_name: str, department_name: str
) -> MiniProgramUser:
    existing = await session.scalar(
        select(MiniProgramUser).where(MiniProgramUser.wechat_openid == openid)
    )
    if existing is not None:
        if not existing.enabled:
            raise AppError("ACCOUNT_DISABLED", "您的账号已被禁用", status_code=403)
        return existing
    if not await ai_search_service.is_mini_program_registration_enabled(session):
        raise AppError(
            "MINI_PROGRAM_REGISTRATION_DISABLED",
            "当前暂未开放新用户绑定，请联系管理员",
            status_code=403,
        )
    user = MiniProgramUser(
        wechat_openid=openid,
        display_name=display_name,
        department_name=department_name,
        enabled=True,
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
    if not item.enabled:
        raise AppError("MATERIAL_DISABLED", "二级库物资已停用", status_code=409)
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
        .where(StockMaterial.enabled.is_(True))
    )
    keyword_condition = contains_any((StockMaterial.name, StockMaterial.model_spec), keyword)
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


def inventory_item_read(item: StockMaterial) -> MiniProgramInventoryItemRead:
    return MiniProgramInventoryItemRead(
        uuid=UUID(item.uuid),
        name=item.name,
        model_spec=item.model_spec,
        unit_name=item.unit.name,
        current_qty=item.balance.quantity if item.balance else Decimal("0"),
        stock_status=_stock_status(item),
    )


def material_read(item: StockMaterial) -> MiniProgramMaterialRead:
    policy = item.replenishment_policy
    return MiniProgramMaterialRead(
        uuid=UUID(item.uuid),
        name=item.name,
        model_spec=item.model_spec,
        unit_name=item.unit.name,
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
        or item.mini_program_user_id != user.id
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


async def recent_outbound_reasons(
    session: AsyncSession, user: MiniProgramUser
) -> tuple[list[str], list[str]]:
    async def list_reasons(user_id: int | None = None) -> list[str]:
        last_used_at = func.max(StockOperation.occurred_at)
        last_operation_id = func.max(StockOperation.id)
        query = (
            select(StockOperation.business_reason)
            .where(
                StockOperation.operation_type == OperationType.OUTBOUND,
                StockOperation.business_reason != "",
            )
            .group_by(StockOperation.business_reason)
            .order_by(last_used_at.desc(), last_operation_id.desc())
            .limit(3)
        )
        if user_id is not None:
            query = query.where(StockOperation.mini_program_user_id == user_id)
        return list((await session.scalars(query)).all())

    personal_reasons = await list_reasons(user.id)
    system_reasons = await list_reasons()
    return personal_reasons, system_reasons


async def create_outbound(
    session: AsyncSession, data: MiniProgramOutboundCreate, user: MiniProgramUser
) -> MiniProgramOutboundRead:
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
