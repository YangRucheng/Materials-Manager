"""匿名分享链接：把勾选的申购计划/申购记录分享为无鉴权页面。

与导出文件的匿名下载同一信任模型：分享 token 为 UUIDv7（不可猜解），
匿名读取端点（GET /shares/{token}）不鉴权，仅凭 token 返回该分享的数据快照。
安全性说明见 app/models/__init__.py 的 ShareLink 与 files.py read_image 注释。

生命周期与清理：
- 创建时按前端选择的失效选项换算 expires_at（NULL = 永久）。
- 读取端点校验：token 不存在或已过期即拒绝（SHARE_NOT_FOUND / SHARE_EXPIRED）。
- 过期行由 cleanup_expired 定期删除（startup + 每日 worker），避免无界增长。
- 创建者可随时 DELETE 撤回（超级管理员亦可），撤回后 token 立即失效。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.errors import AppError, not_found
from app.domain.enums import Role, ShareExpiryOption, ShareType
from app.models import PurchaseMaterial, PurchaseRequestLine, ShareLink, User
from app.schemas import PurchaseMaterialRead, PurchaseRecordRead, SharePublicView
from app.services import material_service, purchase_request_service
from app.services.common import utcnow

logger = logging.getLogger(__name__)

# 失效选项 → 相对时长（None = 永久）。
_EXPIRY_DELTAS: dict[ShareExpiryOption, timedelta | None] = {
    ShareExpiryOption.HOURS_24: timedelta(hours=24),
    ShareExpiryOption.DAYS_3: timedelta(days=3),
    ShareExpiryOption.DAYS_7: timedelta(days=7),
    ShareExpiryOption.DAYS_30: timedelta(days=30),
    ShareExpiryOption.PERMANENT: None,
}

_SHARE_TYPE_LABELS: dict[ShareType, str] = {
    ShareType.PURCHASE_PLAN: "申购计划",
    ShareType.PURCHASE_RECORD: "申购记录",
}

# 分享页可展示列（键名与前端 ShareView 表头一致）。
_SHARE_PLAN_KEYS: frozenset[str] = frozenset(
    {
        "plan_date",
        "material_code",
        "category",
        "urgency",
        "demand_department",
        "name",
        "model_spec",
        "planned_qty",
        "actual_demand_person",
        "purchase_responsible",
        "subitem_no",
        "usage",
        "status",
        "images",
    }
)
_SHARE_RECORD_KEYS: frozenset[str] = frozenset(
    {
        "plan_date",
        "purchase_order_no",
        "trace_no",
        "category",
        "demand_department",
        "material_name",
        "model_spec",
        "purchase_qty",
        "actual_demand_person",
        "purchase_responsible",
        "salesperson",
        "subitem_no",
        "usage",
        "status",
        "images",
    }
)


def _allowed_keys(share_type: ShareType) -> frozenset[str]:
    if share_type == ShareType.PURCHASE_PLAN:
        return _SHARE_PLAN_KEYS
    return _SHARE_RECORD_KEYS


def _validate_columns(share_type: ShareType, columns: list[str] | None) -> list[str] | None:
    """校验展示列：None 表示全部；否则必须非空、无重复、且都是该类型合法键。"""
    if columns is None:
        return None
    allowed = _allowed_keys(share_type)
    invalid = [key for key in columns if key not in allowed]
    if invalid:
        raise AppError(
            "VALIDATION_ERROR",
            f"包含不适用于{_SHARE_TYPE_LABELS[share_type]}的列: {', '.join(invalid)}",
            status_code=422,
        )
    return columns


# 默认展示列：未配置列（columns=NULL）时的展示集合 = 该类型全部列去掉「状态」。
_DEFAULT_EXCLUDED_COLUMNS: frozenset[str] = frozenset({"status"})
# 渲染辅助字段：数量列展示需要计量单位，虽不是可选展示列，但在过滤时始终下发。
_ALWAYS_INCLUDE_COLUMNS: frozenset[str] = frozenset({"unit_name"})


def _resolved_columns(share_type: ShareType, columns: list[str] | None) -> set[str]:
    """把存储的列配置解析为最终展示键集合：None = 默认集合（全部列去掉状态）。"""
    if columns is not None:
        return set(columns)
    return _allowed_keys(share_type) - _DEFAULT_EXCLUDED_COLUMNS


def _expires_at_for(expires_in: ShareExpiryOption) -> datetime | None:
    """把前端选择的失效选项换算为失效时间（naive UTC）；PERMANENT 返回 None。"""
    delta = _EXPIRY_DELTAS[expires_in]
    return None if delta is None else utcnow() + delta


async def create_share(
    session: AsyncSession,
    *,
    share_type: ShareType,
    item_ids: list[int],
    expires_in: ShareExpiryOption,
    created_by: int,
    columns: list[str] | None = None,
) -> ShareLink:
    """创建分享链接：校验勾选项存在后落库，返回持久化的 ShareLink。"""
    ids = sorted(set(item_ids))
    if share_type == ShareType.PURCHASE_PLAN:
        found = set(
            (
                await session.scalars(
                    select(PurchaseMaterial.id).where(PurchaseMaterial.id.in_(ids))
                )
            ).all()
        )
    else:
        found = set(
            (
                await session.scalars(
                    select(PurchaseRequestLine.id).where(PurchaseRequestLine.id.in_(ids))
                )
            ).all()
        )
    if len(found) != len(ids):
        raise not_found(_SHARE_TYPE_LABELS[share_type])
    share = ShareLink(
        share_type=share_type,
        item_ids=ids,
        columns=_validate_columns(share_type, columns),
        expires_at=_expires_at_for(expires_in),
        created_by=created_by,
    )
    session.add(share)
    await session.flush()
    return share


async def get_public_share(session: AsyncSession, *, token: str) -> SharePublicView:
    """匿名读取分享数据：校验 token 存在且未过期，按分享时的 id 实时读取数据快照。

    columns 为 None 时使用默认展示列（全部列去掉「状态」）；否则只返回所选列。
    无论哪种情况都只返回展示列 + 行身份键 + 计量单位，隐藏列数据不下发。
    """
    share = await session.scalar(select(ShareLink).where(ShareLink.token == token))
    if share is None:
        raise AppError("SHARE_NOT_FOUND", "分享链接不存在或已失效", status_code=400)
    if share.expires_at is not None and share.expires_at < utcnow():
        raise AppError("SHARE_EXPIRED", "分享链接已失效，请联系分享人重新分享", status_code=400)
    if share.share_type == ShareType.PURCHASE_PLAN:
        typed_items: list[PurchaseMaterialRead | PurchaseRecordRead] = [
            await material_service.purchase_read(session, item)
            for item in sorted(
                (
                    await session.scalars(
                        select(PurchaseMaterial).where(PurchaseMaterial.id.in_(share.item_ids))
                    )
                ).all(),
                key=lambda row: share.item_ids.index(row.id),
            )
        ]
        identity_key = "id"
    else:
        typed_items = [
            purchase_request_service.purchase_record_read(line)
            for line in sorted(
                (
                    await session.scalars(
                        select(PurchaseRequestLine).where(
                            PurchaseRequestLine.id.in_(share.item_ids)
                        )
                    )
                ).all(),
                key=lambda line: share.item_ids.index(line.id),
            )
        ]
        identity_key = "line_id"
    selected = _resolved_columns(share.share_type, share.columns)
    # 只返回所选列 + 行身份键 + 渲染辅助字段（计量单位），隐藏列数据不下发。
    items = [
        {
            key: value
            for key, value in row.model_dump(mode="json").items()
            if key in selected or key == identity_key or key in _ALWAYS_INCLUDE_COLUMNS
        }
        for row in typed_items
    ]
    return SharePublicView(
        share_type=share.share_type,
        item_count=len(share.item_ids),
        expires_at=share.expires_at,
        created_at=share.created_at,
        columns=share.columns,
        items=items,
    )


async def revoke_share(session: AsyncSession, *, token: str, user: User) -> None:
    """撤回分享：仅创建者本人或超级管理员可执行；撤回后匿名读取立即失效。"""
    share = await session.scalar(select(ShareLink).where(ShareLink.token == token))
    if share is None:
        raise not_found("分享链接")
    if share.created_by != user.id and user.role != Role.SUPER_ADMIN:
        raise AppError("FORBIDDEN", "只能撤回自己创建的分享链接", status_code=403)
    await session.delete(share)
    await session.flush()


async def list_shares(
    session: AsyncSession,
    *,
    user: User,
    page: int,
    page_size: int,
) -> tuple[list[tuple[ShareLink, User | None]], int]:
    """分页列出分享链接：普通用户只看自己创建的，超管看全部；按创建时间倒序。"""
    query = select(ShareLink, User).outerjoin(User, User.id == ShareLink.created_by)
    count_query = select(func.count(ShareLink.id))
    if user.role != Role.SUPER_ADMIN:
        query = query.where(ShareLink.created_by == user.id)
        count_query = count_query.where(ShareLink.created_by == user.id)
    total = int((await session.scalar(count_query)) or 0)
    rows = (
        await session.execute(
            query.order_by(ShareLink.created_at.desc(), ShareLink.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    pairs: list[tuple[ShareLink, User | None]] = []
    for share, creator in rows:
        pairs.append((share, creator))
    return pairs, total


async def update_columns(
    session: AsyncSession,
    *,
    token: str,
    user: User,
    columns: list[str] | None,
) -> ShareLink:
    """更新分享链接的展示列：仅创建者本人或超级管理员可执行。"""
    share = await session.scalar(select(ShareLink).where(ShareLink.token == token))
    if share is None:
        raise not_found("分享链接")
    if share.created_by != user.id and user.role != Role.SUPER_ADMIN:
        raise AppError("FORBIDDEN", "只能修改自己创建的分享链接", status_code=403)
    share.columns = _validate_columns(share.share_type, columns)
    await session.flush()
    return share


async def cleanup_expired() -> int:
    """删除已过期的分享行（startup + 每日 worker 调用），避免表无界增长。"""
    now = utcnow()
    async with SessionLocal() as session:
        expired = list(
            (
                await session.scalars(
                    select(ShareLink).where(ShareLink.expires_at < now)
                )
            ).all()
        )
        if expired:
            await session.execute(
                delete(ShareLink).where(ShareLink.expires_at < now)
            )
            await session.commit()
    return len(expired)


async def run_cleanup_worker(stop_event: asyncio.Event) -> None:
    """每日过期分享清理循环（与 excel 导出清理 worker 同一范式）。"""
    while not stop_event.is_set():
        try:
            purged = await cleanup_expired()
            if purged:
                logger.info("purged %s expired share links", purged)
        except Exception:
            logger.exception("share link cleanup worker crashed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=24 * 60 * 60)
        except TimeoutError:
            pass


__all__ = [
    "create_share",
    "get_public_share",
    "revoke_share",
    "list_shares",
    "update_columns",
    "cleanup_expired",
    "run_cleanup_worker",
]
