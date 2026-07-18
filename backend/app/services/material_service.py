from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.models import (
    FileObject,
    MeasurementUnit,
    PurchaseMaterial,
    PurchaseMaterialImage,
    PurchaseRequestLine,
    StockBalance,
    StockMaterial,
    StockMaterialImage,
    User,
)
from app.schemas import (
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


async def _unit(session: AsyncSession, unit_id: int) -> MeasurementUnit:
    unit = await session.get(MeasurementUnit, unit_id)
    if unit is None or not unit.enabled:
        raise AppError("INVALID_UNIT", "计量单位不存在或已停用")
    return unit


async def _files(session: AsyncSession, image_ids: list[int]) -> list[FileObject]:
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
        enabled=item.enabled,
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


async def create_stock_material(
    session: AsyncSession, data: StockMaterialCreate, user_id: int
) -> StockMaterial:
    unit = await _unit(session, data.unit_id)
    files = await _files(session, data.image_ids)
    item = StockMaterial(
        name=data.name,
        model_spec=data.model_spec,
        unit_id=data.unit_id,
        remark=data.remark,
        identity_hash=identity_hash(data.name, data.model_spec, data.unit_id),
        enabled=True,
        created_by=user_id,
        updated_by=user_id,
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
    session: AsyncSession, item: StockMaterial, data: StockMaterialUpdate, user_id: int
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
    item.updated_by = user_id
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


async def create_purchase_material(
    session: AsyncSession, data: PurchaseMaterialCreate, user_id: int
) -> PurchaseMaterial:
    unit = await _unit(session, data.unit_id)
    current_user_name = await session.scalar(select(User.display_name).where(User.id == user_id))
    responsible = data.purchase_responsible or current_user_name or "待补充"
    validate_quantity_precision(data.planned_qty, unit.decimal_places)
    stock = await _validate_stock_link(session, data.stock_material_id)
    files = await _files(session, data.image_ids)
    item = PurchaseMaterial(
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
        enabled=True,
        created_by=user_id,
        updated_by=user_id,
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
    session: AsyncSession, item: PurchaseMaterial, data: PurchaseMaterialUpdate, user_id: int
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
    if data.actual_demand_person is not None:
        item.actual_demand_person = data.actual_demand_person
    item.purchase_responsible = responsible
    item.identity_hash = identity_hash(data.name, data.model_spec, data.unit_id)
    item.unit = unit
    item.stock_material = stock
    item.images = [
        PurchaseMaterialImage(file_id=file.id, file=file, sort_order=index)
        for index, file in enumerate(files)
    ]
    item.updated_by = user_id
    item.version += 1
    await session.flush()
    return item


async def search_stock_materials(
    session: AsyncSession,
    *,
    keyword: str | None,
    enabled: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[StockMaterial], int]:
    query = select(StockMaterial)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(or_(StockMaterial.name.like(like), StockMaterial.model_spec.like(like)))
    if enabled is not None:
        query = query.where(StockMaterial.enabled == enabled)
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
    enabled: bool | None,
    coded: bool | None,
    moved: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[PurchaseMaterial], int]:
    query = select(PurchaseMaterial)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            or_(
                PurchaseMaterial.name.like(like),
                PurchaseMaterial.model_spec.like(like),
                PurchaseMaterial.material_code.like(like),
            )
        )
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
