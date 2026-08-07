"""二级库物资 / 申购计划的持久化查询边界。

只承载纯 SELECT 查询（含 with_for_update 锁定查询的构造与执行），
不抛业务错误、不组装 read、不自建 session。业务校验与 read 组装留在 service 层。
"""

from uuid import UUID

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import PurchasePlanStatus
from app.models import (
    PurchaseMaterial,
    PurchaseRequestLine,
    StockMaterial,
    StockOperationLine,
)
from app.services.common import contains_any


async def get_stock_material(session: AsyncSession, material_id: int) -> StockMaterial | None:
    result = await session.scalar(
        select(StockMaterial).where(StockMaterial.id == material_id)
    )
    return result if result is not None else None


async def get_stock_material_by_uuid(
    session: AsyncSession, material_uuid: UUID
) -> StockMaterial | None:
    result = await session.scalar(
        select(StockMaterial).where(StockMaterial.uuid == str(material_uuid))
    )
    return result if result is not None else None


async def get_purchase_material(
    session: AsyncSession, material_id: int
) -> PurchaseMaterial | None:
    result = await session.scalar(
        select(PurchaseMaterial).where(PurchaseMaterial.id == material_id)
    )
    return result if result is not None else None


async def stock_material_ids_with_operations(
    session: AsyncSession, material_ids: list[int]
) -> set[int]:
    if not material_ids:
        return set()
    ids = await session.scalars(
        select(StockOperationLine.stock_material_id)
        .where(StockOperationLine.stock_material_id.in_(material_ids))
        .distinct()
    )
    return set(ids.all())


async def purchase_material_ids_moved_to_record(
    session: AsyncSession, ids: list[int]
) -> set[int]:
    """一次性查出哪些申购计划已转入申购记录（列表 read 场景消除 N+1）。"""
    if not ids:
        return set()
    rows = await session.scalars(
        select(PurchaseRequestLine.purchase_material_id)
        .where(PurchaseRequestLine.purchase_material_id.in_(ids))
        .distinct()
    )
    return set(rows.all())


async def search_stock_materials(
    session: AsyncSession,
    *,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[StockMaterial], int]:
    query = select(StockMaterial)
    keyword_condition = contains_any(
        (StockMaterial.name, StockMaterial.name_id, StockMaterial.alias, StockMaterial.model_spec),
        keyword,
    )
    if keyword_condition is not None:
        query = query.where(keyword_condition)
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
    subitem_no: str | None,
    empty_subitem_no: bool,
    category: str | None,
    status: list[PurchasePlanStatus] | None,
    coded: bool | None,
    moved: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[PurchaseMaterial], int]:
    query = select(PurchaseMaterial)
    keyword_condition = contains_any(
        (
            PurchaseMaterial.plan_no,
            cast(PurchaseMaterial.plan_date, String),
            PurchaseMaterial.name,
            PurchaseMaterial.model_spec,
            PurchaseMaterial.material_code,
            PurchaseMaterial.category,
            PurchaseMaterial.unit_name,
            cast(PurchaseMaterial.planned_qty, String),
            PurchaseMaterial.actual_demand_person,
            PurchaseMaterial.purchase_responsible,
            PurchaseMaterial.usage,
            PurchaseMaterial.subitem_no,
            PurchaseMaterial.remark,
        ),
        keyword,
    )
    if keyword_condition is not None:
        query = query.where(keyword_condition)
    if search_field and search_value:
        search_columns = {
            "plan_no": PurchaseMaterial.plan_no,
            "plan_date": cast(PurchaseMaterial.plan_date, String),
            "material_code": PurchaseMaterial.material_code,
            "category": PurchaseMaterial.category,
            "name": PurchaseMaterial.name,
            "model_spec": PurchaseMaterial.model_spec,
            "unit_name": PurchaseMaterial.unit_name,
            "planned_qty": cast(PurchaseMaterial.planned_qty, String),
            "usage": PurchaseMaterial.usage,
            "subitem_no": PurchaseMaterial.subitem_no,
            "remark": PurchaseMaterial.remark,
        }
        search_condition = contains_any((search_columns[search_field],), search_value)
        if search_condition is not None:
            query = query.where(search_condition)
    name_condition = contains_any((PurchaseMaterial.name,), name)
    if name_condition is not None:
        query = query.where(name_condition)
    model_condition = contains_any((PurchaseMaterial.model_spec,), model_spec)
    if model_condition is not None:
        query = query.where(model_condition)
    if empty_actual_demand_person:
        query = query.where(
            or_(
                PurchaseMaterial.actual_demand_person.is_(None),
                func.trim(PurchaseMaterial.actual_demand_person).in_(("", "\\", "/", "—", "-")),
            )
        )
    else:
        demand_person_condition = contains_any(
            (PurchaseMaterial.actual_demand_person,), actual_demand_person
        )
        if demand_person_condition is not None:
            query = query.where(demand_person_condition)
    responsible_condition = contains_any(
        (PurchaseMaterial.purchase_responsible,), purchase_responsible
    )
    if responsible_condition is not None:
        query = query.where(responsible_condition)
    if empty_subitem_no:
        query = query.where(
            or_(PurchaseMaterial.subitem_no.is_(None), func.trim(PurchaseMaterial.subitem_no) == "")
        )
    elif subitem_no:
        query = query.where(func.trim(PurchaseMaterial.subitem_no) == subitem_no.strip())
    if category:
        query = query.where(func.trim(PurchaseMaterial.category) == category.strip())
    if status:
        query = query.where(PurchaseMaterial.status.in_(status))
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
) -> tuple[list[str], list[str], list[str], list[str]]:
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
    subitem_query = select(PurchaseMaterial.subitem_no).where(
        PurchaseMaterial.subitem_no.is_not(None),
        func.trim(PurchaseMaterial.subitem_no) != "",
    )
    category_query = select(PurchaseMaterial.category).where(
        PurchaseMaterial.category.is_not(None),
        func.trim(PurchaseMaterial.category) != "",
    )
    if status is not None:
        actual_demand_query = actual_demand_query.where(PurchaseMaterial.status == status)
        responsible_query = responsible_query.where(PurchaseMaterial.status == status)
        subitem_query = subitem_query.where(PurchaseMaterial.status == status)
        category_query = category_query.where(PurchaseMaterial.status == status)
    if moved is not None:
        moved_filter = record_exists if moved else ~record_exists
        actual_demand_query = actual_demand_query.where(moved_filter)
        responsible_query = responsible_query.where(moved_filter)
        subitem_query = subitem_query.where(moved_filter)
        category_query = category_query.where(moved_filter)
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
    subitem_nos = list(
        await session.scalars(subitem_query.distinct().order_by(PurchaseMaterial.subitem_no))
    )
    categories = list(
        await session.scalars(category_query.distinct().order_by(PurchaseMaterial.category))
    )
    return actual_demand_persons, purchase_responsibles, subitem_nos, categories
