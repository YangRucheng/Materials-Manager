from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.models import PurchaseMaterial, PurchaseRequest, PurchaseRequestLine
from app.schemas import (
    BatchMovePurchasePlansRequest,
    MovePurchasePlanRequest,
    PurchaseMaterialUpdate,
    PurchaseRecordRead,
    PurchaseRecordUpdate,
)
from app.services.common import file_read, utc_aware, validate_version
from app.services.material_service import update_purchase_material

SHANGHAI = timezone(timedelta(hours=8))


def default_purchase_order_no() -> str:
    now = datetime.now(SHANGHAI)
    return f"申购 {now.year}/{now.month}/{now.day}"


def purchase_record_read(line: PurchaseRequestLine) -> PurchaseRecordRead:
    request = line.request
    material = line.purchase_material
    return PurchaseRecordRead(
        line_id=line.id,
        purchase_request_id=request.id,
        purchase_material_id=material.id,
        plan_no=material.plan_no,
        plan_date=material.plan_date,
        purchase_order_no=request.purchase_order_no,
        trace_no=request.trace_no,
        status=line.status,
        material_code=material.material_code,
        material_name=material.name,
        model_spec=material.model_spec,
        unit_id=material.unit_id,
        unit_name=material.unit.name,
        purchase_qty=line.purchase_qty,
        actual_demand_person=material.actual_demand_person,
        purchase_responsible=material.purchase_responsible,
        salesperson=request.salesperson,
        plan_remark=material.remark,
        record_remark=request.remark,
        usage=line.usage,
        subitem_no=line.subitem_no,
        images=[file_read(link.file) for link in material.images],
        stock_material_id=material.stock_material_id,
        purchase_date=request.purchase_date,
        created_at=utc_aware(request.created_at),
        updated_at=utc_aware(max(request.updated_at, material.updated_at)),
        version=request.version,
    )


async def move_plan_to_record(
    session: AsyncSession,
    material_id: int,
    data: MovePurchasePlanRequest,
) -> PurchaseRequestLine:
    return (await move_plans_to_record(session, [material_id], data))[0]


async def batch_move_plans_to_record(
    session: AsyncSession,
    data: BatchMovePurchasePlansRequest,
) -> list[PurchaseRequestLine]:
    return await move_plans_to_record(session, data.material_ids, data)


async def move_plans_to_record(
    session: AsyncSession,
    material_ids: list[int],
    data: MovePurchasePlanRequest,
) -> list[PurchaseRequestLine]:
    ids = sorted(set(material_ids))
    materials = list(
        (
            await session.scalars(
                select(PurchaseMaterial)
                .where(PurchaseMaterial.id.in_(ids))
                .order_by(PurchaseMaterial.id)
                .with_for_update()
            )
        )
        .unique()
        .all()
    )
    if len(materials) != len(ids):
        raise not_found("申购计划")
    uncoded = [material.id for material in materials if not material.material_code]
    if uncoded:
        raise AppError(
            "MATERIAL_CODE_REQUIRED",
            "未编码物资不能转入申购记录",
            status_code=409,
            details={"material_ids": uncoded},
        )
    moved_ids = set(
        (
            await session.scalars(
                select(PurchaseRequestLine.purchase_material_id)
                .where(PurchaseRequestLine.purchase_material_id.in_(ids))
                .with_for_update()
            )
        ).all()
    )
    if moved_ids:
        raise AppError(
            "PLAN_ALREADY_MOVED",
            "部分申购计划已转入申购记录",
            status_code=409,
            details={"material_ids": sorted(moved_ids)},
        )
    request = PurchaseRequest(
        purchase_order_no=(
            data.purchase_order_no or None
            if "purchase_order_no" in data.model_fields_set
            else default_purchase_order_no()
        ),
        trace_no=data.trace_no or None,
        salesperson=data.salesperson,
        remark=data.record_remark,
        purchase_date=data.purchase_date,
        lines=[],
    )
    request.lines = [
        PurchaseRequestLine(
            purchase_material_id=material.id,
            purchase_material=material,
            material_code_snapshot=material.material_code,
            material_name_snapshot=material.name,
            model_spec_snapshot=material.model_spec,
            unit_name_snapshot=material.unit.name,
            purchase_qty=material.planned_qty,
            status=data.status,
            usage=material.usage,
            subitem_no=material.subitem_no,
        )
        for material in materials
    ]
    session.add(request)
    await session.flush()
    return request.lines


async def get_purchase_record(
    session: AsyncSession, line_id: int, *, for_update: bool = False
) -> PurchaseRequestLine:
    query = select(PurchaseRequestLine).where(PurchaseRequestLine.id == line_id)
    if for_update:
        query = query.with_for_update()
    line = await session.scalar(query)
    if line is None:
        raise not_found("申购记录")
    return line


async def update_purchase_record(
    session: AsyncSession,
    line: PurchaseRequestLine,
    data: PurchaseRecordUpdate,
) -> PurchaseRequestLine:
    request = line.request
    material = line.purchase_material
    validate_version(data.version, request.version)
    await update_purchase_material(
        session,
        material,
        PurchaseMaterialUpdate(
            plan_date=data.plan_date,
            material_code=data.material_code,
            name=data.material_name,
            model_spec=data.model_spec,
            unit_id=data.unit_id,
            actual_demand_person=data.actual_demand_person,
            purchase_responsible=data.purchase_responsible,
            planned_qty=data.purchase_qty,
            usage=data.usage,
            subitem_no=data.subitem_no,
            remark=data.plan_remark,
            stock_material_id=data.stock_material_id,
            image_ids=data.image_ids,
            version=material.version,
        ),
    )
    request.purchase_order_no = data.purchase_order_no or None
    request.trace_no = data.trace_no or None
    request.purchase_date = data.purchase_date
    request.salesperson = data.salesperson
    request.remark = data.record_remark
    request.version += 1
    line.material_code_snapshot = material.material_code
    line.material_name_snapshot = material.name
    line.model_spec_snapshot = material.model_spec
    line.unit_name_snapshot = material.unit.name
    line.purchase_qty = data.purchase_qty
    line.status = data.status
    line.usage = data.usage
    line.subitem_no = data.subitem_no
    line.version += 1
    await session.flush()
    return line


async def search_purchase_records(
    session: AsyncSession,
    *,
    status: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[PurchaseRequestLine], int]:
    query = (
        select(PurchaseRequestLine)
        .join(PurchaseRequest, PurchaseRequest.id == PurchaseRequestLine.purchase_request_id)
        .join(PurchaseMaterial, PurchaseMaterial.id == PurchaseRequestLine.purchase_material_id)
    )
    if status:
        query = query.where(PurchaseRequestLine.status == status)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            or_(
                PurchaseRequest.purchase_order_no.like(like),
                PurchaseRequest.trace_no.like(like),
                PurchaseRequest.salesperson.like(like),
                PurchaseRequest.remark.like(like),
                PurchaseRequestLine.status.like(like),
                PurchaseRequestLine.material_code_snapshot.like(like),
                PurchaseRequestLine.material_name_snapshot.like(like),
                PurchaseRequestLine.model_spec_snapshot.like(like),
                PurchaseRequestLine.usage.like(like),
                PurchaseRequestLine.subitem_no.like(like),
                PurchaseMaterial.actual_demand_person.like(like),
                PurchaseMaterial.purchase_responsible.like(like),
                PurchaseMaterial.remark.like(like),
            )
        )
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    items = list(
        (
            await session.scalars(
                query.order_by(PurchaseMaterial.plan_date.desc(), PurchaseRequestLine.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return items, total
