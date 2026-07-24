from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppError, not_found
from app.domain.enums import OperationType, SourceType
from app.models import (
    StockBalance,
    StockMaterial,
    StockOperation,
    StockOperationLine,
    StockReplenishmentPolicy,
)
from app.schemas import (
    InventoryBalanceRead,
    OperationCreate,
    OperationLineWrite,
    OperationUpdate,
    ReverseOperationRequest,
    StockOperationLineRead,
    StockOperationRead,
)
from app.services.common import (
    contains_any,
    log_event,
    utc_aware,
    utc_naive,
    utcnow,
    validate_quantity_precision,
    validate_version,
)

ZERO = Decimal("0")


def _months_before(value: datetime, months: int) -> datetime:
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
) -> StockOperation:
    query = select(StockOperation).where(StockOperation.id == operation_id)
    if for_update:
        query = query.with_for_update()
    item = await session.scalar(query)
    if item is None:
        raise not_found("库存流水")
    return item


async def operation_read(session: AsyncSession, item: StockOperation) -> StockOperationRead:
    return StockOperationRead(
        id=item.id,
        operation_no=item.operation_no,
        operation_type=item.operation_type,
        occurred_at=utc_aware(item.occurred_at),
        business_reason=item.business_reason,
        receiver_name=item.receiver_name,
        subitem_no=item.subitem_no,
        source_type=item.source_type,
        reversal_of_id=item.reversal_of_id,
        client_request_id=item.client_request_id,
        lines=[
            StockOperationLineRead(
                id=line.id,
                stock_material_id=line.stock_material_id,
                material_name=line.material_name_snapshot,
                model_spec=line.model_spec_snapshot,
                unit_name=line.unit_name_snapshot,
                quantity=line.quantity,
                before_qty=line.before_qty,
                after_qty=line.after_qty,
            )
            for line in item.lines
        ],
        created_at=utc_aware(item.created_at),
        version=item.version,
    )


def _operation_snapshot(item: StockOperation) -> dict[str, object]:
    return {
        "operation_type": item.operation_type.value,
        "occurred_at": item.occurred_at.isoformat(),
        "source_type": item.source_type.value,
        "business_reason": item.business_reason,
        "receiver_name": item.receiver_name,
        "subitem_no": item.subitem_no,
        "lines": [
            {
                "stock_material_id": line.stock_material_id,
                "quantity": str(line.quantity),
            }
            for line in item.lines
        ],
    }


async def _lock_and_validate_materials(
    session: AsyncSession,
    lines: Iterable[OperationLineWrite],
    additional_material_ids: Iterable[int] = (),
) -> dict[int, StockMaterial]:
    lines = list(lines)
    new_material_ids = {line.stock_material_id for line in lines}
    material_ids = sorted(new_material_ids | set(additional_material_ids))
    balances = list(
        (
            await session.scalars(
                select(StockBalance)
                .where(StockBalance.stock_material_id.in_(material_ids))
                .order_by(StockBalance.stock_material_id)
                .with_for_update()
            )
        ).all()
    )
    if len(balances) != len(material_ids):
        raise AppError("BALANCE_MISSING", "库存余额记录不存在", status_code=409)
    materials = list(
        (
            await session.scalars(
                select(StockMaterial)
                .where(StockMaterial.id.in_(material_ids))
                .order_by(StockMaterial.id)
                .with_for_update()
            )
        )
        .unique()
        .all()
    )
    by_id = {item.id: item for item in materials}
    missing = [item_id for item_id in material_ids if item_id not in by_id]
    if missing:
        raise AppError("NOT_FOUND", "二级库物资不存在", details={"ids": missing})
    for line in lines:
        validate_quantity_precision(
            line.quantity, by_id[line.stock_material_id].unit.decimal_places
        )
    return by_id


def _validate_operation_semantics(
    operation_type: OperationType,
    source_type: SourceType,
    receiver_name: str | None,
) -> None:
    if source_type == SourceType.INITIALIZATION and operation_type != OperationType.INBOUND:
        raise AppError("INVALID_SOURCE_TYPE", "初始化业务只能是入库")
    if operation_type == OperationType.INBOUND and receiver_name:
        raise AppError("INVALID_RECEIVER", "只有出库业务可以填写领用人")
    if (
        operation_type == OperationType.OUTBOUND
        and source_type != SourceType.REVERSAL
        and not receiver_name
    ):
        raise AppError("RECEIVER_REQUIRED", "出库必须填写领用人")


async def replay_materials(session: AsyncSession, material_ids: Iterable[int]) -> None:
    for material_id in sorted(set(material_ids)):
        balance = await session.get(StockBalance, material_id)
        if balance is None:
            raise AppError("BALANCE_MISSING", "库存余额记录不存在", status_code=409)
        running = ZERO
        rows = (
            await session.execute(
                select(StockOperationLine, StockOperation.operation_type)
                .join(StockOperation, StockOperation.id == StockOperationLine.operation_id)
                .where(StockOperationLine.stock_material_id == material_id)
                .order_by(StockOperation.occurred_at, StockOperation.id, StockOperationLine.id)
            )
        ).all()
        for line, operation_type in rows:
            before = running
            running = (
                running + line.quantity
                if operation_type == OperationType.INBOUND
                else running - line.quantity
            )
            line.before_qty = before
            line.after_qty = running
        balance.quantity = running
        balance.version += 1
        balance.updated_at = utcnow()


async def create_operation(
    session: AsyncSession,
    data: OperationCreate,
    operation_type: OperationType,
    *,
    reversal_of_id: int | None = None,
) -> StockOperation:
    existing = await session.scalar(
        select(StockOperation).where(StockOperation.client_request_id == data.client_request_id)
    )
    if existing is not None:
        return existing
    if data.source_type == SourceType.REVERSAL and reversal_of_id is None:
        raise AppError("INVALID_SOURCE_TYPE", "冲销来源只能由冲销接口创建")
    if operation_type == OperationType.OUTBOUND and not data.business_reason:
        raise AppError("BUSINESS_REASON_REQUIRED", "出库必须填写业务原因")
    _validate_operation_semantics(operation_type, data.source_type, data.receiver_name)
    materials = await _lock_and_validate_materials(session, data.lines)
    existing = cast(
        StockOperation | None,
        await session.scalar(
            select(StockOperation)
            .where(StockOperation.client_request_id == data.client_request_id)
            .with_for_update()
        ),
    )
    if existing is not None:
        return existing
    item = StockOperation(
        operation_no=f"TMP-{uuid4().hex[:20]}",
        operation_type=operation_type,
        occurred_at=utc_naive(data.occurred_at),
        business_reason=data.business_reason,
        receiver_name=data.receiver_name,
        subitem_no=data.subitem_no,
        source_type=data.source_type,
        reversal_of_id=reversal_of_id,
        client_request_id=data.client_request_id,
        lines=[],
    )
    session.add(item)
    await session.flush()
    prefix = "IN" if operation_type == OperationType.INBOUND else "OUT"
    item.operation_no = f"{prefix}{item.occurred_at:%Y%m%d}{item.id:06d}"
    item.lines = [
        StockOperationLine(
            stock_material_id=line.stock_material_id,
            quantity=line.quantity,
            before_qty=ZERO,
            after_qty=ZERO,
            material_name_snapshot=materials[line.stock_material_id].name,
            model_spec_snapshot=materials[line.stock_material_id].model_spec,
            unit_name_snapshot=materials[line.stock_material_id].unit.name,
        )
        for line in data.lines
    ]
    await session.flush()
    await replay_materials(session, materials)
    await log_event(
        session,
        business_type="STOCK_OPERATION",
        business_id=item.id,
        action="CREATED" if reversal_of_id is None else "REVERSED",
        after_data=_operation_snapshot(item),
    )
    await session.flush()
    return item


async def update_operation(
    session: AsyncSession, item: StockOperation, data: OperationUpdate
) -> StockOperation:
    validate_version(data.version, item.version)
    if data.operation_type == OperationType.OUTBOUND and not data.business_reason:
        raise AppError("BUSINESS_REASON_REQUIRED", "出库必须填写业务原因")
    _validate_operation_semantics(data.operation_type, data.source_type, data.receiver_name)
    before = _operation_snapshot(item)
    old_material_ids = {line.stock_material_id for line in item.lines}
    materials = await _lock_and_validate_materials(
        session, data.lines, additional_material_ids=old_material_ids
    )
    item.operation_type = data.operation_type
    item.occurred_at = utc_naive(data.occurred_at)
    item.source_type = data.source_type
    item.business_reason = data.business_reason
    item.receiver_name = data.receiver_name
    item.subitem_no = data.subitem_no
    item.version += 1
    existing_lines = {line.stock_material_id: line for line in item.lines}
    updated_lines: list[StockOperationLine] = []
    for line in data.lines:
        material = materials[line.stock_material_id]
        stored = existing_lines.get(line.stock_material_id)
        if stored is None:
            stored = StockOperationLine(
                stock_material_id=line.stock_material_id,
                before_qty=ZERO,
                after_qty=ZERO,
            )
        stored.quantity = line.quantity
        stored.material_name_snapshot = material.name
        stored.model_spec_snapshot = material.model_spec
        stored.unit_name_snapshot = material.unit.name
        stored.version = stored.version + 1 if stored.id is not None else 1
        updated_lines.append(stored)
    item.lines = updated_lines
    await session.flush()
    await replay_materials(session, old_material_ids | set(materials))
    await log_event(
        session,
        business_type="STOCK_OPERATION",
        business_id=item.id,
        action="UPDATED",
        before_data=before,
        after_data=_operation_snapshot(item),
    )
    return item


async def reverse_operation(
    session: AsyncSession, original: StockOperation, data: ReverseOperationRequest
) -> StockOperation:
    existing = await session.scalar(
        select(StockOperation).where(StockOperation.client_request_id == data.client_request_id)
    )
    if existing:
        return existing
    reversal = await session.scalar(
        select(StockOperation.id).where(StockOperation.reversal_of_id == original.id)
    )
    if reversal:
        raise AppError("ALREADY_REVERSED", "该流水已经冲销", status_code=409)
    reverse_at = max(
        datetime.now(UTC),
        original.occurred_at.replace(tzinfo=UTC) + timedelta(microseconds=1),
    )
    payload = OperationCreate(
        client_request_id=data.client_request_id,
        occurred_at=reverse_at,
        source_type=SourceType.REVERSAL,
        business_reason=data.reason,
        receiver_name=None,
        subitem_no=original.subitem_no,
        lines=[
            OperationLineWrite(
                stock_material_id=line.stock_material_id,
                quantity=line.quantity,
            )
            for line in original.lines
        ],
    )
    reverse_type = (
        OperationType.OUTBOUND
        if original.operation_type == OperationType.INBOUND
        else OperationType.INBOUND
    )
    return await create_operation(session, payload, reverse_type, reversal_of_id=original.id)


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
    if source_type:
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


async def inventory_balances(
    session: AsyncSession,
    *,
    keyword: str | None,
    minimum_qty: Decimal | None,
    maximum_qty: Decimal | None,
    low_stock_only: bool,
    page: int,
    page_size: int,
    material_id: int | None = None,
) -> tuple[list[InventoryBalanceRead], int]:
    query = select(StockMaterial).join(StockBalance)
    if material_id is not None:
        query = query.where(StockMaterial.id == material_id)
    keyword_condition = contains_any((StockMaterial.name, StockMaterial.model_spec), keyword)
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
    recent_consumption = await recent_outbound_consumption(session, (item.id for item in materials))
    result = []
    for item in materials:
        balance = item.balance
        policy = item.replenishment_policy
        current = balance.quantity if balance else ZERO
        low = bool(policy and policy.enabled and current <= policy.minimum_qty)
        suggested = recent_consumption.get(item.id, ZERO)
        result.append(
            InventoryBalanceRead(
                stock_material_id=item.id,
                name=item.name,
                model_spec=item.model_spec,
                unit_name=item.unit.name,
                decimal_places=item.unit.decimal_places,
                current_qty=current,
                minimum_qty=policy.minimum_qty if policy else None,
                is_low_stock=low,
                suggested_purchase_qty=suggested,
                updated_at=utc_aware(balance.updated_at if balance else item.updated_at),
            )
        )
    return result, total
