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
    "model_spec": PurchaseRequestLine.model_spec_snapshot,
    "material_code": PurchaseRequestLine.material_code_snapshot,
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
    "subitem_no": PurchaseRequestLine.subitem_no,
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


async def list_sync_targets(
    session: AsyncSession,
    *,
    limit: int,
    cursor: int,
    fields: set[str] | None = None,
    min_purchase_order_no: str | None = None,
) -> list[tuple[str, int, int]]:
    """按追溯号分组的待同步目标（trace_no 非空且存在缺失字段或未完成状态）。

    返回 (trace_no, target_count, cursor_id) 三元组；cursor 按 line.id 在分组前过滤，
    排序取每组的最大 line.id 倒序。limit 应传 limit+1 由调用方截断判定 has_more。
    fields 为空时覆盖全部同步字段；仅包含调用方实际关心的字段（如新脚本只需
    salesperson/contract_no/vessel_no/status），避免“补不完的字段”长期占用目标。
    min_purchase_order_no 非空时仅保留申购单号 >= 该值的记录（含该值）。
    """
    condition_map = {
        "salesperson": or_(
            PurchaseRequestLine.salesperson.is_(None),
            func.trim(PurchaseRequestLine.salesperson) == "",
        ),
        "contract_no": or_(
            PurchaseRequest.contract_no.is_(None),
            func.trim(PurchaseRequest.contract_no) == "",
        ),
        "vessel_no": or_(
            PurchaseRequest.vessel_no.is_(None),
            func.trim(PurchaseRequest.vessel_no) == "",
        ),
        "consolidation_date": PurchaseRequest.consolidation_date.is_(None),
        "consolidation_port": or_(
            PurchaseRequest.consolidation_port.is_(None),
            func.trim(PurchaseRequest.consolidation_port) == "",
        ),
        "sailing_date": PurchaseRequest.sailing_date.is_(None),
    }
    active_fields = fields or set(condition_map)
    conditions = [condition_map[key] for key in condition_map if key in active_fields]
    if "status" in active_fields:
        conditions.append(PurchaseRequestLine.status.in_(("已申购", "已采购", "部分入库")))

    where_clauses = [
        PurchaseRequestLine.trace_no.is_not(None),
        func.trim(PurchaseRequestLine.trace_no) != "",
        or_(*conditions),
    ]
    if min_purchase_order_no:
        where_clauses.append(
            func.trim(PurchaseRequest.purchase_order_no) >= min_purchase_order_no
        )

    query = (
        select(
            PurchaseRequestLine.trace_no,
            func.count().label("target_count"),
            func.max(PurchaseRequestLine.id).label("cursor_id"),
        )
        .join(PurchaseRequest, PurchaseRequest.id == PurchaseRequestLine.purchase_request_id)
        .where(*where_clauses)
        .group_by(PurchaseRequestLine.trace_no)
        .order_by(func.max(PurchaseRequestLine.id).desc(), PurchaseRequestLine.trace_no)
    )
    if cursor:
        query = query.where(PurchaseRequestLine.id < cursor)
    rows = (await session.execute(query.limit(limit + 1))).all()
    return [(row.trace_no, int(row.target_count), int(row.cursor_id)) for row in rows]


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
    subitem_no: str | None,
    empty_subitem_no: bool,
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
    if empty_subitem_no:
        query = query.where(
            or_(
                PurchaseRequestLine.subitem_no.is_(None),
                func.trim(PurchaseRequestLine.subitem_no) == "",
            )
        )
    elif subitem_no:
        query = query.where(func.trim(PurchaseRequestLine.subitem_no) == subitem_no.strip())
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


async def search_mini_program_purchase_records(
    session: AsyncSession,
    *,
    keyword: str | None = None,
    status: str | None = None,
    subitem_no: str | None = None,
    page: int = 1,
    page_size: int = 15,
) -> tuple[list[PurchaseRequestLine], int]:
    """小程序申购记录列表：keyword 仅 OR 匹配 名称/型号/追溯号/申购单号。"""
    query = select(PurchaseRequestLine).join(
        PurchaseRequest, PurchaseRequest.id == PurchaseRequestLine.purchase_request_id
    )
    keyword_condition = contains_any(
        (
            PurchaseRequestLine.material_name_snapshot,
            PurchaseRequestLine.model_spec_snapshot,
            PurchaseRequestLine.trace_no,
            PurchaseRequest.purchase_order_no,
        ),
        keyword,
    )
    if keyword_condition is not None:
        query = query.where(keyword_condition)
    if status:
        query = query.where(func.trim(PurchaseRequestLine.status) == status.strip())
    if subitem_no:
        query = query.where(func.trim(PurchaseRequestLine.subitem_no) == subitem_no.strip())
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    items = list(
        (
            await session.scalars(
                query.order_by(PurchaseRequestLine.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
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


async def purchase_subitem_options(session: AsyncSession) -> list[str]:
    return [
        item
        for item in (
            await session.scalars(
                select(PurchaseRequestLine.subitem_no)
                .where(
                    PurchaseRequestLine.subitem_no.is_not(None),
                    func.trim(PurchaseRequestLine.subitem_no) != "",
                )
                .distinct()
                .order_by(PurchaseRequestLine.subitem_no)
            )
        ).all()
        if item is not None
    ]


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
