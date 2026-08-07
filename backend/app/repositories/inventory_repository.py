"""库存出入库流水 / 余额的持久化查询边界。

只承载纯 SELECT 查询（含 with_for_update 锁定查询的构造与执行），
不抛业务错误、不组装 read、不自建 session。业务校验与 read 组装留在 service 层。
"""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.enums import OperationType, SourceType
from app.models import (
    StockBalance,
    StockMaterial,
    StockOperation,
    StockOperationLine,
    StockReplenishmentPolicy,
)
from app.services.common import contains_any, utcnow


def _months_before(value: datetime, months: int) -> datetime:
    from calendar import monthrange

    month_index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


async def recent_outbound_consumption(
    session: AsyncSession,
    material_ids: Iterable[int],
    *,
    now: datetime | None = None,
) -> dict[int, Decimal]:
    ids = list(dict.fromkeys(material_ids))
    if not ids:
        return {}
    end_at = now or utcnow()
    start_at = _months_before(end_at, 6)
    reversal = aliased(StockOperation)
    rows = await session.execute(
        select(
            StockOperationLine.stock_material_id,
            func.sum(StockOperationLine.quantity),
        )
        .join(StockOperation, StockOperation.id == StockOperationLine.operation_id)
        .outerjoin(reversal, reversal.reversal_of_id == StockOperation.id)
        .where(
            StockOperationLine.stock_material_id.in_(ids),
            StockOperation.operation_type == OperationType.OUTBOUND,
            StockOperation.source_type != SourceType.REVERSAL,
            StockOperation.occurred_at >= start_at,
            StockOperation.occurred_at <= end_at,
            reversal.id.is_(None),
        )
        .group_by(StockOperationLine.stock_material_id)
    )
    return {material_id: quantity for material_id, quantity in rows.all()}


async def get_operation(
    session: AsyncSession, operation_id: int, *, for_update: bool = False
) -> StockOperation | None:
    query = select(StockOperation).where(StockOperation.id == operation_id)
    if for_update:
        query = query.with_for_update()
    result = await session.scalar(query)
    return result if result is not None else None


async def search_operations(
    session: AsyncSession,
    *,
    operation_no: str | None,
    operation_type: OperationType | None,
    material_name: str | None,
    source_type: SourceType | None,
    start_at: datetime | None,
    end_at: datetime | None,
    page: int,
    page_size: int,
) -> tuple[list[StockOperation], int]:
    query = select(StockOperation)
    if operation_no:
        query = query.where(StockOperation.operation_no.like(f"%{operation_no}%"))
    if operation_type:
        query = query.where(StockOperation.operation_type == operation_type)
    if material_name:
        query = query.join(StockOperationLine)
    material_condition = contains_any(
        (StockOperationLine.material_name_snapshot, StockOperationLine.model_spec_snapshot),
        material_name,
    )
    if material_condition is not None:
        query = query.where(material_condition)
    if source_type == SourceType.MINI_PROGRAM:
        query = query.where(StockOperation.mini_program_user_name_snapshot.is_not(None))
    elif source_type == SourceType.MANUAL:
        query = query.where(
            StockOperation.source_type == SourceType.MANUAL,
            StockOperation.mini_program_user_name_snapshot.is_(None),
        )
    elif source_type:
        query = query.where(StockOperation.source_type == source_type)
    if start_at:
        query = query.where(StockOperation.occurred_at >= start_at)
    if end_at:
        query = query.where(StockOperation.occurred_at <= end_at)
    query = query.distinct()
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    items = list(
        (
            await session.scalars(
                query.order_by(StockOperation.occurred_at.desc(), StockOperation.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return items, total


async def search_inventory_materials(
    session: AsyncSession,
    *,
    keyword: str | None,
    minimum_qty: Decimal | None,
    maximum_qty: Decimal | None,
    low_stock_only: bool,
    page: int,
    page_size: int,
    material_id: int | None = None,
) -> tuple[list[StockMaterial], int]:
    """库存物资分页查询（不含 read 组装），供 inventory_balances 使用。"""
    query = select(StockMaterial).join(StockBalance)
    if material_id is not None:
        query = query.where(StockMaterial.id == material_id)
    keyword_condition = contains_any(
        (StockMaterial.name, StockMaterial.alias, StockMaterial.model_spec), keyword
    )
    if keyword_condition is not None:
        query = query.where(keyword_condition)
    if minimum_qty is not None:
        query = query.where(StockBalance.quantity >= minimum_qty)
    if maximum_qty is not None:
        query = query.where(StockBalance.quantity <= maximum_qty)
    if low_stock_only:
        query = query.join(StockReplenishmentPolicy).where(
            StockReplenishmentPolicy.enabled.is_(True),
            StockBalance.quantity <= StockReplenishmentPolicy.minimum_qty,
        )
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    materials = list(
        (
            await session.scalars(
                query.order_by(StockMaterial.id).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return materials, total
