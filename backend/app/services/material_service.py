from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.domain.enums import PurchasePlanStatus
from app.models import (
    FileObject,
    MeasurementUnit,
    PurchaseMaterial,
    PurchaseMaterialImage,
    PurchaseRequestLine,
    StockBalance,
    StockMaterial,
    StockMaterialImage,
)
from app.schemas import (
    BatchUpdatePurchasePlansRequest,
    PurchaseMaterialCreate,
    PurchaseMaterialRead,
    PurchaseMaterialUpdate,
    StockMaterialCreate,
    StockMaterialRead,
    StockMaterialUpdate,
)
from app.services.common import (
    file_read,
    identity_hash,
    utc_aware,
    validate_quantity_precision,
    validate_version,
)

SHANGHAI = timezone(timedelta(hours=8))


async def _unit(session: AsyncSession, unit_id: int) -> MeasurementUnit:
    unit = await session.get(MeasurementUnit, unit_id)
    if unit is None or not unit.enabled:
        raise AppError("INVALID_UNIT", "计量单位不存在或已停用")
    return unit


async def _files(session: AsyncSession, image_ids: list[str]) -> list[FileObject]:
    if not image_ids:
        return []
    files = list(
        (await session.scalars(select(FileObject).where(FileObject.id.in_(image_ids)))).all()
    )
    by_id = {item.id: item for item in files}
    missing = [item_id for item_id in image_ids if item_id not in by_id]
    if missing:
        raise AppError("INVALID_IMAGE_ID", "图片不存在", details={"file_ids": missing})
    return [by_id[item_id] for item_id in image_ids]


def stock_read(item: StockMaterial) -> StockMaterialRead:
    return StockMaterialRead(
        id=item.id,
        name=item.name,
        model_spec=item.model_spec,
        unit_id=item.unit_id,
        unit_name=item.unit.name,
        remark=item.remark,
        current_qty=item.balance.quantity if item.balance else 0,
        images=[file_read(link.file) for link in item.images],
        replenishment_policy=item.replenishment_policy,
        created_at=utc_aware(item.created_at),
        updated_at=utc_aware(item.updated_at),
        version=item.version,
    )


async def get_stock_material(session: AsyncSession, material_id: int) -> StockMaterial:
    item = await session.scalar(select(StockMaterial).where(StockMaterial.id == material_id))
    if item is None:
        raise not_found("二级库物资")
    return item


async def create_stock_material(session: AsyncSession, data: StockMaterialCreate) -> StockMaterial:
    unit = await _unit(session, data.unit_id)
    files = await _files(session, data.image_ids)
    item = StockMaterial(
        name=data.name,
        model_spec=data.model_spec,
        unit_id=data.unit_id,
        remark=data.remark,
        identity_hash=identity_hash(data.name, data.model_spec, data.unit_id),
        enabled=True,
    )
    item.unit = unit
    item.balance = StockBalance(quantity=0)
    item.replenishment_policy = None
    item.images = [
        StockMaterialImage(file_id=file.id, file=file, sort_order=index)
        for index, file in enumerate(files)
    ]
    session.add(item)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(
            "DUPLICATE_MATERIAL", "相同名称、型号规格和单位的物资已存在", status_code=409
        ) from exc
    return item


async def update_stock_material(
    session: AsyncSession, item: StockMaterial, data: StockMaterialUpdate
) -> StockMaterial:
    validate_version(data.version, item.version)
    unit = await _unit(session, data.unit_id)
    files = await _files(session, data.image_ids)
    item.name = data.name
    item.model_spec = data.model_spec
    item.unit_id = data.unit_id
    item.unit = unit
    item.remark = data.remark
    item.identity_hash = identity_hash(data.name, data.model_spec, data.unit_id)
    item.images = [
        StockMaterialImage(file_id=file.id, file=file, sort_order=index)
        for index, file in enumerate(files)
    ]
    item.version += 1
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(
            "DUPLICATE_MATERIAL", "相同名称、型号规格和单位的物资已存在", status_code=409
        ) from exc
    return item


async def get_purchase_material(session: AsyncSession, material_id: int) -> PurchaseMaterial:
    item = await session.scalar(select(PurchaseMaterial).where(PurchaseMaterial.id == material_id))
    if item is None:
        raise not_found("申购计划")
    return item


async def purchase_read(session: AsyncSession, item: PurchaseMaterial) -> PurchaseMaterialRead:
    moved_to_record = bool(
        await session.scalar(
            select(PurchaseRequestLine.id)
            .where(PurchaseRequestLine.purchase_material_id == item.id)
            .limit(1)
        )
    )
    return PurchaseMaterialRead(
        id=item.id,
        plan_no=item.plan_no,
        plan_date=item.plan_date,
        material_code=item.material_code,
        name=item.name,
        model_spec=item.model_spec,
        unit_id=item.unit_id,
        unit_name=item.unit.name,
        actual_demand_person=item.actual_demand_person,
        purchase_responsible=item.purchase_responsible,
        planned_qty=item.planned_qty,
        usage=item.usage,
        subitem_no=item.subitem_no,
        remark=item.remark,
        stock_material_id=item.stock_material_id,
        stock_material_name=item.stock_material.name if item.stock_material else None,
        status=item.status,
        moved_to_record=moved_to_record,
        enabled=item.enabled,
        images=[file_read(link.file) for link in item.images],
        created_at=utc_aware(item.created_at),
        updated_at=utc_aware(item.updated_at),
        version=item.version,
    )


async def _validate_stock_link(
    session: AsyncSession, stock_material_id: int | None
) -> StockMaterial | None:
    if stock_material_id is None:
        return None
    stock = await session.get(StockMaterial, stock_material_id)
    if stock is None:
        raise not_found("二级库物资")
    return stock


async def _next_plan_no(session: AsyncSession, plan_date: date) -> str:
    prefix = f"PLAN-{plan_date:%Y%m%d}-"
    previous = await session.scalar(
        select(PurchaseMaterial.plan_no)
        .where(PurchaseMaterial.plan_date == plan_date)
        .order_by(PurchaseMaterial.plan_no.desc())
        .limit(1)
        .with_for_update()
    )
    index = int(previous.rsplit("-", 1)[-1]) + 1 if previous else 1
    if index > 999:
        raise AppError(
            "PLAN_DAILY_LIMIT_EXCEEDED",
            "同一计划日期最多创建 999 条申购计划",
            status_code=409,
        )
    return f"{prefix}{index:03d}"


async def create_purchase_material(
    session: AsyncSession, data: PurchaseMaterialCreate
) -> PurchaseMaterial:
    unit = await _unit(session, data.unit_id)
    responsible = data.purchase_responsible or "\\"
    validate_quantity_precision(data.planned_qty, unit.decimal_places)
    stock = await _validate_stock_link(session, data.stock_material_id)
    files = await _files(session, data.image_ids)
    plan_date = data.plan_date or datetime.now(SHANGHAI).date()
    item = PurchaseMaterial(
        plan_no=await _next_plan_no(session, plan_date),
        plan_date=plan_date,
        material_code=data.material_code,
        name=data.name,
        model_spec=data.model_spec,
        unit_id=data.unit_id,
        actual_demand_person=data.actual_demand_person or responsible,
        purchase_responsible=responsible,
        planned_qty=data.planned_qty,
        usage=data.usage,
        subitem_no=data.subitem_no,
        remark=data.remark,
        stock_material_id=data.stock_material_id,
        identity_hash=identity_hash(data.name, data.model_spec, data.unit_id),
        status=data.status,
        enabled=True,
        images=[
            PurchaseMaterialImage(file_id=file.id, file=file, sort_order=index)
            for index, file in enumerate(files)
        ],
    )
    item.unit = unit
    item.stock_material = stock
    session.add(item)
    await session.flush()
    return item


async def update_purchase_material(
    session: AsyncSession, item: PurchaseMaterial, data: PurchaseMaterialUpdate
) -> PurchaseMaterial:
    validate_version(data.version, item.version)
    unit = await _unit(session, data.unit_id)
    responsible = data.purchase_responsible or item.purchase_responsible
    validate_quantity_precision(data.planned_qty, unit.decimal_places)
    stock = await _validate_stock_link(session, data.stock_material_id)
    files = await _files(session, data.image_ids)
    for key in (
        "material_code",
        "name",
        "model_spec",
        "unit_id",
        "planned_qty",
        "usage",
        "subitem_no",
        "remark",
        "stock_material_id",
    ):
        setattr(item, key, getattr(data, key))
    if data.plan_date is not None and data.plan_date != item.plan_date:
        item.plan_no = await _next_plan_no(session, data.plan_date)
        item.plan_date = data.plan_date
    if data.actual_demand_person is not None:
        item.actual_demand_person = data.actual_demand_person
    if "status" in data.model_fields_set:
        item.status = data.status
    item.purchase_responsible = responsible
    item.identity_hash = identity_hash(data.name, data.model_spec, data.unit_id)
    item.unit = unit
    item.stock_material = stock
    item.images = [
        PurchaseMaterialImage(file_id=file.id, file=file, sort_order=index)
        for index, file in enumerate(files)
    ]
    item.version += 1
    await session.flush()
    return item


async def batch_update_purchase_materials(
    session: AsyncSession, data: BatchUpdatePurchasePlansRequest
) -> list[PurchaseMaterial]:
    material_ids = [reference.id for reference in data.materials]
    items = list(
        (
            await session.scalars(
                select(PurchaseMaterial)
                .where(PurchaseMaterial.id.in_(material_ids))
                .with_for_update()
            )
        )
        .unique()
        .all()
    )
    items_by_id = {item.id: item for item in items}
    if len(items_by_id) != len(material_ids):
        raise not_found("申购计划")

    update_fields = data.model_fields_set & {
        "plan_date",
        "actual_demand_person",
        "subitem_no",
        "usage",
        "status",
    }
    updated: list[PurchaseMaterial] = []
    for reference in data.materials:
        item = items_by_id[reference.id]
        validate_version(reference.version, item.version)
        if "plan_date" in update_fields and data.plan_date != item.plan_date:
            assert data.plan_date is not None
            item.plan_no = await _next_plan_no(session, data.plan_date)
            item.plan_date = data.plan_date
        if "actual_demand_person" in update_fields:
            assert data.actual_demand_person is not None
            item.actual_demand_person = data.actual_demand_person
        if "subitem_no" in update_fields:
            item.subitem_no = data.subitem_no
        if "usage" in update_fields:
            assert data.usage is not None
            item.usage = data.usage
        if "status" in update_fields:
            assert data.status is not None
            item.status = data.status
        item.version += 1
        await session.flush()
        updated.append(item)
    return updated


async def delete_purchase_material(
    session: AsyncSession, item: PurchaseMaterial, version: int
) -> None:
    validate_version(version, item.version)
    referenced = await session.scalar(
        select(PurchaseRequestLine.id)
        .where(PurchaseRequestLine.purchase_material_id == item.id)
        .limit(1)
    )
    if referenced is not None:
        raise AppError(
            "PURCHASE_PLAN_IN_USE",
            "已转入申购记录的计划不能删除",
            status_code=409,
        )
    await session.delete(item)
    await session.flush()


async def search_stock_materials(
    session: AsyncSession,
    *,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[StockMaterial], int]:
    query = select(StockMaterial)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(or_(StockMaterial.name.like(like), StockMaterial.model_spec.like(like)))
    count = await session.scalar(select(func.count()).select_from(query.subquery()))
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
    return items, int(count or 0)


async def search_purchase_materials(
    session: AsyncSession,
    *,
    keyword: str | None,
    search_field: str | None,
    search_value: str | None,
    name: str | None,
    model_spec: str | None,
    actual_demand_person: str | None,
    empty_actual_demand_person: bool,
    purchase_responsible: str | None,
    status: PurchasePlanStatus | None,
    enabled: bool | None,
    coded: bool | None,
    moved: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[PurchaseMaterial], int]:
    query = select(PurchaseMaterial).join(
        MeasurementUnit, MeasurementUnit.id == PurchaseMaterial.unit_id
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            or_(
                PurchaseMaterial.plan_no.like(like),
                cast(PurchaseMaterial.plan_date, String).like(like),
                PurchaseMaterial.name.like(like),
                PurchaseMaterial.model_spec.like(like),
                PurchaseMaterial.material_code.like(like),
                MeasurementUnit.name.like(like),
                cast(PurchaseMaterial.planned_qty, String).like(like),
                PurchaseMaterial.actual_demand_person.like(like),
                PurchaseMaterial.purchase_responsible.like(like),
                PurchaseMaterial.usage.like(like),
                PurchaseMaterial.subitem_no.like(like),
                PurchaseMaterial.remark.like(like),
            )
        )
    if search_field and search_value:
        search_columns = {
            "plan_no": PurchaseMaterial.plan_no,
            "plan_date": cast(PurchaseMaterial.plan_date, String),
            "material_code": PurchaseMaterial.material_code,
            "name": PurchaseMaterial.name,
            "model_spec": PurchaseMaterial.model_spec,
            "unit_name": MeasurementUnit.name,
            "planned_qty": cast(PurchaseMaterial.planned_qty, String),
            "usage": PurchaseMaterial.usage,
            "subitem_no": PurchaseMaterial.subitem_no,
            "remark": PurchaseMaterial.remark,
        }
        query = query.where(search_columns[search_field].like(f"%{search_value}%"))
    if name:
        query = query.where(PurchaseMaterial.name.like(f"%{name}%"))
    if model_spec:
        query = query.where(PurchaseMaterial.model_spec.like(f"%{model_spec}%"))
    if empty_actual_demand_person:
        query = query.where(
            or_(
                PurchaseMaterial.actual_demand_person.is_(None),
                func.trim(PurchaseMaterial.actual_demand_person).in_(("", "\\", "/", "—", "-")),
            )
        )
    elif actual_demand_person:
        query = query.where(PurchaseMaterial.actual_demand_person.like(f"%{actual_demand_person}%"))
    if purchase_responsible:
        query = query.where(PurchaseMaterial.purchase_responsible.like(f"%{purchase_responsible}%"))
    if status is not None:
        query = query.where(PurchaseMaterial.status == status)
    if enabled is not None:
        query = query.where(PurchaseMaterial.enabled == enabled)
    if coded is True:
        query = query.where(PurchaseMaterial.material_code.is_not(None))
    elif coded is False:
        query = query.where(PurchaseMaterial.material_code.is_(None))
    if moved is not None:
        record_exists = (
            select(PurchaseRequestLine.id)
            .where(PurchaseRequestLine.purchase_material_id == PurchaseMaterial.id)
            .exists()
        )
        query = query.where(record_exists if moved else ~record_exists)
    count = await session.scalar(select(func.count()).select_from(query.subquery()))
    items = list(
        (
            await session.scalars(
                query.order_by(PurchaseMaterial.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return items, int(count or 0)


async def purchase_filter_options(
    session: AsyncSession,
    *,
    moved: bool | None,
    status: PurchasePlanStatus | None,
) -> tuple[list[str], list[str]]:
    record_exists = (
        select(PurchaseRequestLine.id)
        .where(PurchaseRequestLine.purchase_material_id == PurchaseMaterial.id)
        .exists()
    )
    actual_demand_query = select(PurchaseMaterial.actual_demand_person).where(
        ~func.trim(PurchaseMaterial.actual_demand_person).in_(("", "\\", "/", "—", "-"))
    )
    responsible_query = select(PurchaseMaterial.purchase_responsible).where(
        func.trim(PurchaseMaterial.purchase_responsible) != ""
    )
    if status is not None:
        actual_demand_query = actual_demand_query.where(PurchaseMaterial.status == status)
        responsible_query = responsible_query.where(PurchaseMaterial.status == status)
    if moved is not None:
        moved_filter = record_exists if moved else ~record_exists
        actual_demand_query = actual_demand_query.where(moved_filter)
        responsible_query = responsible_query.where(moved_filter)
    actual_demand_persons = list(
        await session.scalars(
            actual_demand_query.distinct().order_by(PurchaseMaterial.actual_demand_person)
        )
    )
    purchase_responsibles = list(
        await session.scalars(
            responsible_query.distinct().order_by(PurchaseMaterial.purchase_responsible)
        )
    )
    return actual_demand_persons, purchase_responsibles


async def purchase_materials_for_export(
    session: AsyncSession,
    *,
    material_ids: list[int] | None = None,
    keyword: str | None = None,
    coded: bool | None = None,
    moved: bool | None = None,
    status: PurchasePlanStatus | None = None,
) -> list[PurchaseMaterial]:
    query = select(PurchaseMaterial)
    if material_ids is not None:
        query = query.where(PurchaseMaterial.id.in_(material_ids))
    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            or_(
                PurchaseMaterial.name.like(like),
                PurchaseMaterial.model_spec.like(like),
                PurchaseMaterial.material_code.like(like),
                PurchaseMaterial.plan_no.like(like),
            )
        )
    if coded is True:
        query = query.where(PurchaseMaterial.material_code.is_not(None))
    elif coded is False:
        query = query.where(PurchaseMaterial.material_code.is_(None))
    if status is not None:
        query = query.where(PurchaseMaterial.status == status)
    if moved is not None:
        record_exists = (
            select(PurchaseRequestLine.id)
            .where(PurchaseRequestLine.purchase_material_id == PurchaseMaterial.id)
            .exists()
        )
        query = query.where(record_exists if moved else ~record_exists)
    items = list((await session.scalars(query.order_by(PurchaseMaterial.id))).unique().all())
    if material_ids is not None and len(items) != len(set(material_ids)):
        raise not_found("申购计划")
    return items
