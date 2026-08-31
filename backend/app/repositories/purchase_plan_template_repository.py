"""周期性计划（申购计划模板）的持久化查询边界。

只承载纯 SELECT 查询，不抛业务错误、不组装 read、不自建 session。
业务校验与 read 组装留在 service 层。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PurchasePlanTemplate
from app.services.common import contains_any

# 列表可排序列白名单：sort_by 参数经此映射到 ORM 列（防止任意属性注入）。
PURCHASE_PLAN_TEMPLATE_SORT_COLUMNS = {
    "material_code": PurchasePlanTemplate.material_code,
    "category": PurchasePlanTemplate.category,
    "urgency": PurchasePlanTemplate.urgency,
    "demand_department": PurchasePlanTemplate.demand_department,
    "name": PurchasePlanTemplate.name,
    "model_spec": PurchasePlanTemplate.model_spec,
    "unit_name": PurchasePlanTemplate.unit_name,
    "actual_demand_person": PurchasePlanTemplate.actual_demand_person,
    "purchase_responsible": PurchasePlanTemplate.purchase_responsible,
    "planned_qty": PurchasePlanTemplate.planned_qty,
    "subitem_no": PurchasePlanTemplate.subitem_no,
    "usage": PurchasePlanTemplate.usage,
}


async def search_templates(
    session: AsyncSession,
    *,
    keyword: str | None,
    name: str | None,
    model_spec: str | None,
    actual_demand_person: str | None,
    purchase_responsible: str | None,
    category: str | None,
    page: int,
    page_size: int,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> tuple[list[PurchasePlanTemplate], int]:
    query = select(PurchasePlanTemplate)
    keyword_condition = contains_any(
        (
            PurchasePlanTemplate.name,
            PurchasePlanTemplate.model_spec,
            PurchasePlanTemplate.material_code,
            PurchasePlanTemplate.category,
            PurchasePlanTemplate.unit_name,
            PurchasePlanTemplate.actual_demand_person,
            PurchasePlanTemplate.purchase_responsible,
            PurchasePlanTemplate.usage,
            PurchasePlanTemplate.subitem_no,
        ),
        keyword,
    )
    if keyword_condition is not None:
        query = query.where(keyword_condition)
    name_condition = contains_any((PurchasePlanTemplate.name,), name)
    if name_condition is not None:
        query = query.where(name_condition)
    model_condition = contains_any((PurchasePlanTemplate.model_spec,), model_spec)
    if model_condition is not None:
        query = query.where(model_condition)
    demand_person_condition = contains_any(
        (PurchasePlanTemplate.actual_demand_person,), actual_demand_person
    )
    if demand_person_condition is not None:
        query = query.where(demand_person_condition)
    responsible_condition = contains_any(
        (PurchasePlanTemplate.purchase_responsible,), purchase_responsible
    )
    if responsible_condition is not None:
        query = query.where(responsible_condition)
    if category:
        query = query.where(func.trim(PurchasePlanTemplate.category) == category.strip())

    count = await session.scalar(select(func.count()).select_from(query.subquery()))
    direction = asc if sort_order == "asc" else desc
    order_terms: list[Any] = (
        [
            direction(PURCHASE_PLAN_TEMPLATE_SORT_COLUMNS[sort_by]),
            PurchasePlanTemplate.id.desc(),
        ]
        if sort_by and sort_by in PURCHASE_PLAN_TEMPLATE_SORT_COLUMNS
        else [PurchasePlanTemplate.id.desc()]
    )
    items = list(
        (
            await session.scalars(
                query.order_by(*order_terms).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return items, int(count or 0)


async def template_filter_options(
    session: AsyncSession,
) -> tuple[list[str], list[str], list[str]]:
    actual_demand_query = select(PurchasePlanTemplate.actual_demand_person).where(
        ~func.trim(PurchasePlanTemplate.actual_demand_person).in_(("", "\\", "/", "—", "-"))
    )
    responsible_query = select(PurchasePlanTemplate.purchase_responsible).where(
        func.trim(PurchasePlanTemplate.purchase_responsible) != ""
    )
    category_query = select(PurchasePlanTemplate.category).where(
        PurchasePlanTemplate.category.is_not(None),
        func.trim(PurchasePlanTemplate.category) != "",
    )
    actual_demand_persons = list(
        await session.scalars(
            actual_demand_query.distinct().order_by(PurchasePlanTemplate.actual_demand_person)
        )
    )
    purchase_responsibles = list(
        await session.scalars(
            responsible_query.distinct().order_by(PurchasePlanTemplate.purchase_responsible)
        )
    )
    categories = list(
        await session.scalars(category_query.distinct().order_by(PurchasePlanTemplate.category))
    )
    return actual_demand_persons, purchase_responsibles, categories
