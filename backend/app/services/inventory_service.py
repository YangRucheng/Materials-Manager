from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.domain.enums import (
    ON_ORDER_REQUEST_STATUSES,
    OperationType,
    PurchaseRequestStatus,
    SourceType,
)
from app.models import (
    PurchaseMaterial,
    PurchaseRequest,
    PurchaseRequestLine,
    StockBalance,
    StockMaterial,
    StockOperation,
    StockOperationLine,
    StockReplenishmentPolicy,
    User,
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
    log_event,
    utc_aware,
    utc_naive,
    utcnow,
    validate_quantity_precision,
    validate_version,
)

ZERO = Decimal("0")


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
    from app.models import User

    operator_name = await session.scalar(
        select(User.display_name).where(User.id == item.operator_id)
    )
    request_no = None
    request_line_id = next(
        (line.purchase_request_line_id for line in item.lines if line.purchase_request_line_id),
        None,
    )
    if request_line_id:
        request_no = await session.scalar(
            select(PurchaseRequest.trace_no)
            .join(PurchaseRequestLine)
            .where(PurchaseRequestLine.id == request_line_id)
        )
    return StockOperationRead(
        id=item.id,
        operation_no=item.operation_no,
        operation_type=item.operation_type,
        occurred_at=utc_aware(item.occurred_at),
        operator_name=operator_name or "未知用户",
        business_reason=item.business_reason,
        receiver_name=item.receiver_name,
        subitem_no=item.subitem_no,
        source_type=item.source_type,
        reversal_of_id=item.reversal_of_id,
        purchase_request_no=request_no,
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
                purchase_request_line_id=line.purchase_request_line_id,
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
                "purchase_request_line_id": line.purchase_request_line_id,
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
    disabled = [item.id for item in materials if item.id in new_material_ids and not item.enabled]
    if disabled:
        raise AppError("MATERIAL_DISABLED", "停用物资不能新增库存业务", details={"ids": disabled})
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
    if source_type == SourceType.PURCHASE_RECEIPT and operation_type != OperationType.INBOUND:
        raise AppError("INVALID_SOURCE_TYPE", "申购到货只能是入库")
    if operation_type == OperationType.INBOUND and receiver_name:
        raise AppError("INVALID_RECEIVER", "只有出库业务可以填写领用人")
    if (
        operation_type == OperationType.OUTBOUND
        and source_type != SourceType.REVERSAL
        and not receiver_name
    ):
        raise AppError("RECEIVER_REQUIRED", "出库必须填写领用人")


async def _lock_and_validate_receipts(
    session: AsyncSession,
    *,
    lines: Iterable[OperationLineWrite],
    operation_type: OperationType,
    source_type: SourceType,
    materials: dict[int, StockMaterial],
    exclude_operation_id: int | None = None,
    additional_request_line_ids: Iterable[int] = (),
) -> set[int]:
    lines = list(lines)
    receipt_lines = [line for line in lines if line.purchase_request_line_id is not None]
    if not receipt_lines:
        if source_type == SourceType.PURCHASE_RECEIPT:
            raise AppError("PURCHASE_LINE_REQUIRED", "申购到货入库必须关联申购记录")
        additional_ids = sorted(set(additional_request_line_ids))
        if additional_ids:
            await session.scalars(
                select(PurchaseRequestLine)
                .where(PurchaseRequestLine.id.in_(additional_ids))
                .order_by(PurchaseRequestLine.id)
                .with_for_update()
            )
        return set(additional_ids)
    if source_type not in {SourceType.PURCHASE_RECEIPT, SourceType.REVERSAL}:
        raise AppError("INVALID_PURCHASE_RECEIPT_SOURCE", "关联申购记录时来源必须为申购到货或冲销")
    if operation_type != OperationType.INBOUND and source_type != SourceType.REVERSAL:
        raise AppError("INVALID_PURCHASE_RECEIPT_TYPE", "只有入库可以作为申购到货")
    new_request_line_ids = {
        line.purchase_request_line_id
        for line in receipt_lines
        if line.purchase_request_line_id is not None
    }
    request_line_ids = sorted(
        {
            *new_request_line_ids,
            *additional_request_line_ids,
        }
    )
    if len(new_request_line_ids) != len(receipt_lines):
        raise AppError("DUPLICATE_PURCHASE_LINE", "同一流水不能重复关联同一申购记录")
    request_lines = list(
        (
            await session.scalars(
                select(PurchaseRequestLine)
                .where(PurchaseRequestLine.id.in_(request_line_ids))
                .order_by(PurchaseRequestLine.id)
                .with_for_update()
            )
        )
        .unique()
        .all()
    )
    by_id = {item.id: item for item in request_lines}
    if len(by_id) != len(request_line_ids):
        raise not_found("申购记录明细")
    for line in receipt_lines:
        request_line_id = line.purchase_request_line_id
        if request_line_id is None:
            continue
        request_line = by_id[request_line_id]
        request = request_line.request
        if request.status not in {
            PurchaseRequestStatus.SUBMITTED,
            PurchaseRequestStatus.PROCESSING,
            PurchaseRequestStatus.PARTIALLY_RECEIVED,
            PurchaseRequestStatus.COMPLETED,
        }:
            raise AppError(
                "INVALID_STATUS_TRANSITION",
                "当前申购记录状态不能登记到货",
                status_code=409,
                details={"request_id": request.id, "status": request.status.value},
            )
        purchase_material = request_line.purchase_material
        if purchase_material.stock_material_id is None:
            purchase_material.stock_material_id = line.stock_material_id
            purchase_material.version += 1
        elif purchase_material.stock_material_id != line.stock_material_id:
            raise AppError(
                "PURCHASE_MATERIAL_MISMATCH",
                "申购记录与二级库物资关联不一致",
                details={
                    "purchase_request_line_id": request_line.id,
                    "expected_stock_material_id": purchase_material.stock_material_id,
                    "actual_stock_material_id": line.stock_material_id,
                },
            )
        validate_quantity_precision(
            line.quantity, materials[line.stock_material_id].unit.decimal_places
        )

        # 修改流水时排除旧流水，创建时以当前已到货量校验。
        already = ZERO
        result = await session.execute(
            select(
                StockOperation.id,
                StockOperation.operation_type,
                StockOperationLine.quantity,
            )
            .join(StockOperationLine)
            .where(StockOperationLine.purchase_request_line_id == request_line.id)
        )
        for operation_id, receipt_type, quantity in result:
            if operation_id == exclude_operation_id:
                continue
            already += quantity if receipt_type == OperationType.INBOUND else -quantity
        projected = (
            already + line.quantity
            if operation_type == OperationType.INBOUND
            else already - line.quantity
        )
        if projected < ZERO:
            raise AppError(
                "NEGATIVE_RECEIPT",
                "累计到货数量不能为负数",
                status_code=409,
                details={
                    "purchase_request_line_id": request_line.id,
                    "received": str(already),
                    "requested": str(line.quantity),
                },
            )
    return set(request_line_ids)


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


async def recompute_receipts(
    session: AsyncSession, request_line_ids: Iterable[int], user_id: int
) -> None:
    request_ids: set[int] = set()
    for line_id in sorted(set(request_line_ids)):
        request_line = await session.scalar(
            select(PurchaseRequestLine).where(PurchaseRequestLine.id == line_id).with_for_update()
        )
        if request_line is None:
            continue
        received = ZERO
        rows = await session.execute(
            select(StockOperation.operation_type, StockOperationLine.quantity)
            .join(StockOperationLine)
            .where(StockOperationLine.purchase_request_line_id == line_id)
        )
        for operation_type, quantity in rows:
            received += quantity if operation_type == OperationType.INBOUND else -quantity
        if received < ZERO:
            raise AppError(
                "NEGATIVE_RECEIPT",
                "申购累计到货数量不能为负数",
                status_code=409,
                details={
                    "purchase_request_line_id": line_id,
                    "requested_qty": str(request_line.requested_qty),
                    "received_qty": str(received),
                },
            )
        request_line.received_qty = received
        request_line.version += 1
        request_ids.add(request_line.purchase_request_id)

    for request_id in sorted(request_ids):
        request = await session.scalar(
            select(PurchaseRequest).where(PurchaseRequest.id == request_id).with_for_update()
        )
        if request is None or request.status in {
            PurchaseRequestStatus.CLOSED,
            PurchaseRequestStatus.CANCELED,
        }:
            continue
        old = request.status
        if request.lines and all(line.received_qty >= line.requested_qty for line in request.lines):
            request.status = PurchaseRequestStatus.COMPLETED
            request.completed_at = utcnow()
        elif any(line.received_qty > ZERO for line in request.lines):
            request.status = PurchaseRequestStatus.PARTIALLY_RECEIVED
            request.completed_at = None
        else:
            request.status = (
                PurchaseRequestStatus.PROCESSING
                if request.handler_id
                else PurchaseRequestStatus.SUBMITTED
            )
            request.completed_at = None
        if request.status != old:
            request.version += 1
            await log_event(
                session,
                business_type="PURCHASE_REQUEST",
                business_id=request.id,
                action="RECEIPT_STATUS_UPDATED",
                user_id=user_id,
                old_status=old.value,
                new_status=request.status.value,
            )


async def create_operation(
    session: AsyncSession,
    data: OperationCreate,
    operation_type: OperationType,
    user_id: int,
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
    request_line_ids = await _lock_and_validate_receipts(
        session,
        lines=data.lines,
        operation_type=operation_type,
        source_type=data.source_type,
        materials=materials,
    )
    item = StockOperation(
        operation_no=f"TMP-{uuid4().hex[:20]}",
        operation_type=operation_type,
        occurred_at=utc_naive(data.occurred_at),
        operator_id=user_id,
        business_reason=data.business_reason,
        receiver_name=data.receiver_name,
        subitem_no=data.subitem_no,
        source_type=data.source_type,
        reversal_of_id=reversal_of_id,
        client_request_id=data.client_request_id,
        created_by=user_id,
        updated_by=user_id,
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
            purchase_request_line_id=line.purchase_request_line_id,
            created_by=user_id,
            updated_by=user_id,
        )
        for line in data.lines
    ]
    await session.flush()
    await replay_materials(session, materials)
    await recompute_receipts(session, request_line_ids, user_id)
    await log_event(
        session,
        business_type="STOCK_OPERATION",
        business_id=item.id,
        action="CREATED" if reversal_of_id is None else "REVERSED",
        user_id=user_id,
        after_data=_operation_snapshot(item),
    )
    await session.flush()
    return item


async def update_operation(
    session: AsyncSession, item: StockOperation, data: OperationUpdate, user_id: int
) -> StockOperation:
    validate_version(data.version, item.version)
    if data.operation_type == OperationType.OUTBOUND and not data.business_reason:
        raise AppError("BUSINESS_REASON_REQUIRED", "出库必须填写业务原因")
    _validate_operation_semantics(data.operation_type, data.source_type, data.receiver_name)
    before = _operation_snapshot(item)
    old_material_ids = {line.stock_material_id for line in item.lines}
    old_request_line_ids = {
        int(line.purchase_request_line_id) for line in item.lines if line.purchase_request_line_id
    }
    materials = await _lock_and_validate_materials(
        session, data.lines, additional_material_ids=old_material_ids
    )
    new_request_line_ids = await _lock_and_validate_receipts(
        session,
        lines=data.lines,
        operation_type=data.operation_type,
        source_type=data.source_type,
        materials=materials,
        exclude_operation_id=item.id,
        additional_request_line_ids=old_request_line_ids,
    )
    item.operation_type = data.operation_type
    item.occurred_at = utc_naive(data.occurred_at)
    item.source_type = data.source_type
    item.business_reason = data.business_reason
    item.receiver_name = data.receiver_name
    item.subitem_no = data.subitem_no
    item.updated_by = user_id
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
                created_by=user_id,
            )
        stored.quantity = line.quantity
        stored.material_name_snapshot = material.name
        stored.model_spec_snapshot = material.model_spec
        stored.unit_name_snapshot = material.unit.name
        stored.purchase_request_line_id = line.purchase_request_line_id
        stored.updated_by = user_id
        stored.version = stored.version + 1 if stored.id is not None else 1
        updated_lines.append(stored)
    item.lines = updated_lines
    await session.flush()
    await replay_materials(session, old_material_ids | set(materials))
    await recompute_receipts(session, old_request_line_ids | new_request_line_ids, user_id)
    await log_event(
        session,
        business_type="STOCK_OPERATION",
        business_id=item.id,
        action="UPDATED",
        user_id=user_id,
        before_data=before,
        after_data=_operation_snapshot(item),
    )
    return item


async def reverse_operation(
    session: AsyncSession, original: StockOperation, data: ReverseOperationRequest, user_id: int
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
                purchase_request_line_id=line.purchase_request_line_id,
            )
            for line in original.lines
        ],
    )
    reverse_type = (
        OperationType.OUTBOUND
        if original.operation_type == OperationType.INBOUND
        else OperationType.INBOUND
    )
    return await create_operation(
        session, payload, reverse_type, user_id, reversal_of_id=original.id
    )


async def search_operations(
    session: AsyncSession,
    *,
    operation_no: str | None,
    operation_type: OperationType | None,
    material_name: str | None,
    operator_name: str | None,
    purchase_request_no: str | None,
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
    if material_name or purchase_request_no:
        query = query.join(StockOperationLine)
    if material_name:
        query = query.where(StockOperationLine.material_name_snapshot.like(f"%{material_name}%"))
    if operator_name:
        query = query.join(User, User.id == StockOperation.operator_id).where(
            User.display_name.like(f"%{operator_name}%")
        )
    if purchase_request_no:
        query = (
            query.join(
                PurchaseRequestLine,
                PurchaseRequestLine.id == StockOperationLine.purchase_request_line_id,
            )
            .join(PurchaseRequest, PurchaseRequest.id == PurchaseRequestLine.purchase_request_id)
            .where(PurchaseRequest.trace_no.like(f"%{purchase_request_no}%"))
        )
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
    if keyword:
        like = f"%{keyword}%"
        query = query.where(or_(StockMaterial.name.like(like), StockMaterial.model_spec.like(like)))
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
    material_ids = [item.id for item in materials]
    on_order: defaultdict[int, Decimal] = defaultdict(lambda: ZERO)
    if material_ids:
        rows = await session.execute(
            select(
                PurchaseMaterial.stock_material_id,
                PurchaseRequestLine.requested_qty,
                PurchaseRequestLine.received_qty,
            )
            .join(
                PurchaseRequestLine, PurchaseRequestLine.purchase_material_id == PurchaseMaterial.id
            )
            .join(PurchaseRequest, PurchaseRequest.id == PurchaseRequestLine.purchase_request_id)
            .where(
                PurchaseMaterial.stock_material_id.in_(material_ids),
                PurchaseRequest.status.in_(ON_ORDER_REQUEST_STATUSES),
            )
        )
        for stock_id, requested, received in rows:
            if stock_id is not None:
                on_order[stock_id] += requested - received
    result = []
    for item in materials:
        balance = item.balance
        policy = item.replenishment_policy
        current = balance.quantity if balance else ZERO
        order_qty = on_order[item.id]
        low = bool(policy and policy.enabled and current <= policy.minimum_qty)
        suggested = max((policy.target_qty if policy else ZERO) - current - order_qty, ZERO)
        result.append(
            InventoryBalanceRead(
                stock_material_id=item.id,
                name=item.name,
                model_spec=item.model_spec,
                unit_name=item.unit.name,
                decimal_places=item.unit.decimal_places,
                current_qty=current,
                minimum_qty=policy.minimum_qty if policy else None,
                target_qty=policy.target_qty if policy else None,
                on_order_qty=order_qty,
                is_low_stock=low,
                warning_state=("ON_ORDER" if order_qty > ZERO else "PENDING_PURCHASE")
                if low
                else None,
                suggested_purchase_qty=suggested,
                updated_at=utc_aware(balance.updated_at if balance else item.updated_at),
            )
        )
    return result, total
