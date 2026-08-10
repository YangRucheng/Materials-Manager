"""申购记录（PurchaseRequest / PurchaseRequestLine）的持久化查询边界。

只承载纯 SELECT 查询（含 with_for_update 锁定查询的构造与执行），
不抛业务错误、不组装 read、不自建 session。业务校验与 read 组装留在 service 层。
"""

from typing import Any

from sqlalchemy import String, asc, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PurchaseRequest, PurchaseRequestLine
from app.services.common import contains_any

# 申购记录列表可排序列白名单：sort_by 参数经此映射到对应表的 ORM 列（防止任意属性注入）。
# 记录查询 join 头表与行表，各列须落在正确表上。材料字段均取自行表快照列
#（记录自包含，不再依赖已清理的申购计划）。
PURCHASE_RECORD_SORT_COLUMNS = {
    "plan_date": PurchaseRequestLine.plan_date_snapshot,
    "category": PurchaseRequestLine.category_snapshot,
    "demand_department": PurchaseRequestLine.demand_department_snapshot,
    "material_name": PurchaseRequestLine.material_name_snapshot,
    "actual_demand_person": PurchaseRequestLine.actual_demand_person_snapshot,
    "purchase_responsible": PurchaseRequestLine.purchase_responsible_snapshot,
    "purchase_date": PurchaseRequest.purchase_date,
    "purchase_order_no": PurchaseRequest.purchase_order_no,
    "contract_no": PurchaseRequest.contract_no,
    "vessel_no": PurchaseRequest.vessel_no,
    "consolidation_date": PurchaseRequest.consolidation_date,
    "consolidation_port": PurchaseRequest.consolidation_port,
    "sailing_date": PurchaseRequest.sailing_date,
    "trace_no": PurchaseRequestLine.trace_no,
    "purchase_qty": PurchaseRequestLine.purchase_qty,
    "usage": PurchaseRequestLine.usage,
    "salesperson": PurchaseRequestLine.salesperson,
    "status": PurchaseRequestLine.status,
}


async def get_purchase_record(
    session: AsyncSession, line_id: int, *, for_update: bool = False
) -> PurchaseRequestLine | None:
    query = select(PurchaseRequestLine).where(PurchaseRequestLine.id == line_id)
    if for_update:
        query = query.with_for_update()
    result = await session.scalar(query)
    return result if result is not None else None


async def search_purchase_records(
    session: AsyncSession,
    *,
    status: str | None,
    empty_status: bool,
    keyword: str | None,
    search_field: str | None,
    search_value: str | None,
    purchase_order_no: str | None,
    trace_no: str | None,
    category: str | None,
    name: str | None,
    model_spec: str | None,
    actual_demand_person: str | None,
    purchase_responsible: str | None,
    salesperson: str | None,
    page: int,
    page_size: int,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> tuple[list[PurchaseRequestLine], int]:
    query = (
        select(PurchaseRequestLine)
        .join(PurchaseRequest, PurchaseRequest.id == PurchaseRequestLine.purchase_request_id)
    )
    if empty_status:
        query = query.where(
            or_(PurchaseRequestLine.status.is_(None), func.trim(PurchaseRequestLine.status) == "")
        )
    elif status:
        query = query.where(PurchaseRequestLine.status == status)
    keyword_condition = contains_any(
        (
            PurchaseRequest.purchase_order_no,
            PurchaseRequestLine.trace_no,
            PurchaseRequest.contract_no,
            PurchaseRequest.vessel_no,
            cast(PurchaseRequest.consolidation_date, String),
            PurchaseRequest.consolidation_port,
            cast(PurchaseRequest.sailing_date, String),
            PurchaseRequestLine.salesperson,
            PurchaseRequest.remark,
            PurchaseRequestLine.plan_no_snapshot,
            cast(PurchaseRequestLine.plan_date_snapshot, String),
            PurchaseRequestLine.status,
            PurchaseRequestLine.material_code_snapshot,
            PurchaseRequestLine.category_snapshot,
            PurchaseRequestLine.material_name_snapshot,
            PurchaseRequestLine.model_spec_snapshot,
            PurchaseRequestLine.unit_name_snapshot,
            cast(PurchaseRequestLine.purchase_qty, String),
            PurchaseRequestLine.usage,
            PurchaseRequestLine.subitem_no,
            PurchaseRequestLine.actual_demand_person_snapshot,
            PurchaseRequestLine.purchase_responsible_snapshot,
            PurchaseRequestLine.plan_remark_snapshot,
            cast(PurchaseRequest.purchase_date, String),
        ),
        keyword,
    )
    if keyword_condition is not None:
        query = query.where(keyword_condition)
    if search_field and search_value:
        search_columns = {
            "plan_no": PurchaseRequestLine.plan_no_snapshot,
            "plan_date": cast(PurchaseRequestLine.plan_date_snapshot, String),
            "purchase_order_no": PurchaseRequest.purchase_order_no,
            "trace_no": PurchaseRequestLine.trace_no,
            "contract_no": PurchaseRequest.contract_no,
            "vessel_no": PurchaseRequest.vessel_no,
            "consolidation_date": cast(PurchaseRequest.consolidation_date, String),
            "consolidation_port": PurchaseRequest.consolidation_port,
            "sailing_date": cast(PurchaseRequest.sailing_date, String),
            "category": PurchaseRequestLine.category_snapshot,
            "material_code": PurchaseRequestLine.material_code_snapshot,
            "material_name": PurchaseRequestLine.material_name_snapshot,
            "model_spec": PurchaseRequestLine.model_spec_snapshot,
            "unit_name": PurchaseRequestLine.unit_name_snapshot,
            "purchase_qty": cast(PurchaseRequestLine.purchase_qty, String),
            "salesperson": PurchaseRequestLine.salesperson,
            "status": PurchaseRequestLine.status,
            "purchase_date": cast(PurchaseRequest.purchase_date, String),
            "usage": PurchaseRequestLine.usage,
            "subitem_no": PurchaseRequestLine.subitem_no,
            "plan_remark": PurchaseRequestLine.plan_remark_snapshot,
            "record_remark": PurchaseRequest.remark,
        }
        search_condition = contains_any((search_columns[search_field],), search_value)
        if search_condition is not None:
            query = query.where(search_condition)
    if category:
        query = query.where(
            func.trim(PurchaseRequestLine.category_snapshot) == category.strip()
        )
    field_filters = (
        ((PurchaseRequest.purchase_order_no,), purchase_order_no),
        ((PurchaseRequestLine.trace_no,), trace_no),
        ((PurchaseRequestLine.material_name_snapshot,), name),
        ((PurchaseRequestLine.model_spec_snapshot,), model_spec),
        ((PurchaseRequestLine.actual_demand_person_snapshot,), actual_demand_person),
        ((PurchaseRequestLine.purchase_responsible_snapshot,), purchase_responsible),
        (
            (PurchaseRequestLine.salesperson,),
            salesperson,
        ),
    )
    for columns, value in field_filters:
        condition = contains_any(columns, value)
        if condition is not None:
            query = query.where(condition)
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    direction = asc if sort_order == "asc" else desc
    if sort_by and sort_by in PURCHASE_RECORD_SORT_COLUMNS:
        order_terms: list[Any] = [
            direction(PURCHASE_RECORD_SORT_COLUMNS[sort_by]),
            PurchaseRequestLine.id.desc(),
        ]
    else:
        # 默认序：申购单号 → 追溯号 空值置后降序，再按行 id 倒序（稳定分页）。
        order_terms = [
            or_(
                PurchaseRequest.purchase_order_no.is_(None),
                func.trim(PurchaseRequest.purchase_order_no) == "",
            ),
            PurchaseRequest.purchase_order_no.desc(),
            or_(
                PurchaseRequestLine.trace_no.is_(None),
                func.trim(PurchaseRequestLine.trace_no) == "",
            ),
            PurchaseRequestLine.trace_no.desc(),
            PurchaseRequestLine.id.desc(),
        ]
    items = list(
        (
            await session.scalars(
                query.order_by(*order_terms).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return items, total


async def purchase_salesperson_options(session: AsyncSession) -> list[str]:
    salesperson = func.trim(PurchaseRequestLine.salesperson)
    return list(
        await session.scalars(
            select(PurchaseRequestLine.salesperson)
            .where(
                PurchaseRequestLine.salesperson.is_not(None),
                salesperson != "",
            )
            .distinct()
            .order_by(PurchaseRequestLine.salesperson)
        )
    )


async def purchase_status_options(session: AsyncSession) -> list[str]:
    return list(
        await session.scalars(
            select(PurchaseRequestLine.status)
            .where(
                PurchaseRequestLine.status.is_not(None),
                func.trim(PurchaseRequestLine.status) != "",
            )
            .distinct()
            .order_by(PurchaseRequestLine.status)
        )
    )


async def purchase_record_filter_options(
    session: AsyncSession,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """记录页筛选下拉：从行表快照列取 distinct 值（记录自包含，不依赖已清理的计划）。"""
    actual_demand_query = select(
        PurchaseRequestLine.actual_demand_person_snapshot
    ).where(
        ~func.trim(PurchaseRequestLine.actual_demand_person_snapshot).in_(("", "\\", "/", "—", "-"))
    )
    responsible_query = select(PurchaseRequestLine.purchase_responsible_snapshot).where(
        func.trim(PurchaseRequestLine.purchase_responsible_snapshot) != ""
    )
    subitem_query = select(PurchaseRequestLine.subitem_no).where(
        PurchaseRequestLine.subitem_no.is_not(None),
        func.trim(PurchaseRequestLine.subitem_no) != "",
    )
    category_query = select(PurchaseRequestLine.category_snapshot).where(
        PurchaseRequestLine.category_snapshot.is_not(None),
        func.trim(PurchaseRequestLine.category_snapshot) != "",
    )
    actual_demand_persons = list(
        await session.scalars(
            actual_demand_query.distinct().order_by(
                PurchaseRequestLine.actual_demand_person_snapshot
            )
        )
    )
    purchase_responsibles = list(
        await session.scalars(
            responsible_query.distinct().order_by(
                PurchaseRequestLine.purchase_responsible_snapshot
            )
        )
    )
    subitem_nos = [
        item
        for item in (
            await session.scalars(
                subitem_query.distinct().order_by(PurchaseRequestLine.subitem_no)
            )
        ).all()
        if item is not None
    ]
    categories = [
        item
        for item in (
            await session.scalars(
                category_query.distinct().order_by(PurchaseRequestLine.category_snapshot)
            )
        ).all()
        if item is not None
    ]
    return actual_demand_persons, purchase_responsibles, subitem_nos, categories
