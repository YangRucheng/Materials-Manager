from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.enums import ON_ORDER_REQUEST_STATUSES
from app.models import (
    PurchaseMaterial,
    PurchaseRequest,
    PurchaseRequestLine,
    StockMaterial,
    StockReplenishmentPolicy,
)
from app.schemas import (
    PurchaseMaterialCreate,
    ReplenishmentDraftCreate,
    ReplenishmentDraftRead,
    ReplenishmentPolicyWrite,
)
from app.services.common import validate_quantity_precision, validate_version
from app.services.material_service import create_purchase_material, get_stock_material

ZERO = Decimal("0")


async def set_policy(
    session: AsyncSession,
    material: StockMaterial,
    data: ReplenishmentPolicyWrite,
    user_id: int,
) -> StockMaterial:
    validate_quantity_precision(data.minimum_qty, material.unit.decimal_places)
    policy = material.replenishment_policy
    if policy is None:
        policy = StockReplenishmentPolicy(
            stock_material_id=material.id,
            minimum_qty=data.minimum_qty,
            enabled=data.enabled,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(policy)
        material.replenishment_policy = policy
    else:
        validate_version(data.version, policy.version)
        policy.minimum_qty = data.minimum_qty
        policy.enabled = data.enabled
        policy.updated_by = user_id
        policy.version += 1
    await session.flush()
    return material


async def create_replenishment_draft(
    session: AsyncSession,
    stock_material_id: int,
    data: ReplenishmentDraftCreate,
    user_id: int,
) -> ReplenishmentDraftRead:
    stock = await get_stock_material(session, stock_material_id)
    if stock.balance is None:
        raise AppError("BALANCE_MISSING", "库存余额记录不存在", status_code=409)
    policy = stock.replenishment_policy
    if policy is None or not policy.enabled or stock.balance.quantity > policy.minimum_qty:
        raise AppError("NOT_LOW_STOCK", "该物资当前不在低库存范围", status_code=409)

    rows = await session.execute(
        select(PurchaseRequestLine.requested_qty, PurchaseRequestLine.received_qty)
        .join(PurchaseRequest, PurchaseRequest.id == PurchaseRequestLine.purchase_request_id)
        .join(PurchaseMaterial, PurchaseMaterial.id == PurchaseRequestLine.purchase_material_id)
        .where(
            PurchaseMaterial.stock_material_id == stock.id,
            PurchaseRequest.status.in_(ON_ORDER_REQUEST_STATUSES),
        )
    )
    on_order = sum((requested - received for requested, received in rows), start=ZERO)
    suggested = max(policy.minimum_qty - stock.balance.quantity - on_order, ZERO)
    if suggested == ZERO:
        raise AppError(
            "REPLENISHMENT_NOT_REQUIRED",
            "现有在途数量已覆盖最低库存，无需重复发起",
            status_code=409,
        )
    validate_quantity_precision(data.planned_qty, stock.unit.decimal_places)

    previous_code = await session.scalar(
        select(PurchaseMaterial.material_code)
        .where(
            PurchaseMaterial.stock_material_id == stock.id,
            PurchaseMaterial.material_code.is_not(None),
        )
        .order_by(PurchaseMaterial.id.desc())
        .limit(1)
    )
    quantity_note = f"补库计划：建议申购 {suggested} {stock.unit.name}"
    if data.planned_qty != suggested:
        quantity_note += f"，确认计划 {data.planned_qty} {stock.unit.name}"
    note_parts = [part for part in [stock.remark, quantity_note] if part]
    purchase = await create_purchase_material(
        session,
        PurchaseMaterialCreate(
            material_code=previous_code,
            name=stock.name,
            model_spec=stock.model_spec,
            unit_id=stock.unit_id,
            actual_demand_person=data.actual_demand_person,
            purchase_responsible=data.purchase_responsible,
            planned_qty=data.planned_qty,
            usage="低库存补库",
            remark="；".join(note_parts),
            stock_material_id=stock.id,
            image_ids=[link.file_id for link in stock.images],
        ),
        user_id,
    )
    return ReplenishmentDraftRead(next="purchase_material", resource_id=purchase.id)
