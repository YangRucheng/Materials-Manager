from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import (
    PurchaseMaterial,
    StockMaterial,
    StockReplenishmentPolicy,
)
from app.schemas import (
    PurchaseMaterialCreate,
    ReplenishmentDefaultsRead,
    ReplenishmentDraftCreate,
    ReplenishmentDraftRead,
    ReplenishmentPolicyWrite,
)
from app.services.common import validate_quantity_precision, validate_version
from app.services.inventory_service import recent_outbound_consumption
from app.services.material_service import create_purchase_material, get_stock_material

ZERO = Decimal("0")
SHANGHAI = timezone(timedelta(hours=8))


async def replenishment_defaults(session: AsyncSession) -> ReplenishmentDefaultsRead:
    latest_responsible = await session.scalar(
        select(PurchaseMaterial.purchase_responsible)
        .where(
            func.trim(PurchaseMaterial.purchase_responsible).not_in(("", "\\", "/", "—", "-"))
        )
        .order_by(PurchaseMaterial.id.desc())
        .limit(1)
    )
    return ReplenishmentDefaultsRead(
        purchase_responsible=latest_responsible or "",
        demand_date=datetime.now(SHANGHAI).date(),
    )


async def set_policy(
    session: AsyncSession,
    material: StockMaterial,
    data: ReplenishmentPolicyWrite,
) -> StockMaterial:
    validate_quantity_precision(data.minimum_qty, material.unit.decimal_places)
    policy = material.replenishment_policy
    if policy is None:
        policy = StockReplenishmentPolicy(
            stock_material_id=material.id,
            minimum_qty=data.minimum_qty,
            enabled=data.enabled,
        )
        session.add(policy)
        material.replenishment_policy = policy
    else:
        validate_version(data.version, policy.version)
        policy.minimum_qty = data.minimum_qty
        policy.enabled = data.enabled
        policy.version += 1
    await session.flush()
    return material


async def create_replenishment_draft(
    session: AsyncSession,
    stock_material_id: int,
    data: ReplenishmentDraftCreate,
) -> ReplenishmentDraftRead:
    stock = await get_stock_material(session, stock_material_id)
    if stock.balance is None:
        raise AppError("BALANCE_MISSING", "库存余额记录不存在", status_code=409)
    policy = stock.replenishment_policy
    if policy is None or not policy.enabled or stock.balance.quantity > policy.minimum_qty:
        raise AppError("NOT_LOW_STOCK", "该物资当前不在低库存范围", status_code=409)

    suggested = (await recent_outbound_consumption(session, [stock.id])).get(stock.id, ZERO)
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
            plan_date=data.demand_date,
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
    )
    return ReplenishmentDraftRead(next="purchase_material", resource_id=purchase.id)
