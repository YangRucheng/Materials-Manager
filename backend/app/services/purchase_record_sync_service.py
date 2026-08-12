"""申购记录同步（外部物资平台数据回写）专用服务。

替代被移除的 /agent/database/execute：只暴露「待同步目标列表」与「按追溯号回写」两个
窄操作，不允许任意 SQL。语义与旧油猴脚本一致：文本字段仅当空才填、日期仅当 NULL 才填、
状态只进不退，且只在实际变更时自增 version（updated_at 由 ORM onupdate 自动更新）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.models import PurchaseRequest, PurchaseRequestLine
from app.repositories import purchase_request_repository
from app.schemas import (
    PurchaseRecordSyncResultRead,
    PurchaseRecordSyncTargetRead,
    PurchaseRecordSyncTargetsRead,
    PurchaseRecordSyncTraceUpdate,
)

# 状态只进不退：目标状态 -> 允许的当前状态集合（不在集合里的目标值不生效）
_STATUS_PROGRESSION = {
    "已入库": {"已申购", "已采购", "部分入库", "已入库"},
    "部分入库": {"已申购", "已采购", "部分入库"},
    "已采购": {"已申购", "已采购"},
}


_SYNC_FIELDS = frozenset(
    {
        "salesperson",
        "contract_no",
        "vessel_no",
        "consolidation_port",
        "consolidation_date",
        "sailing_date",
        "status",
    }
)


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


async def list_sync_targets(
    session: AsyncSession,
    *,
    limit: int,
    cursor: int,
    fields: str | None = None,
    min_purchase_order_no: str | None = None,
) -> PurchaseRecordSyncTargetsRead:
    active_fields: set[str] | None = None
    if fields:
        parsed = {part.strip() for part in fields.split(",") if part.strip()}
        unknown = parsed - _SYNC_FIELDS
        if unknown:
            raise AppError(
                "VALIDATION_ERROR",
                f"未知同步字段: {', '.join(sorted(unknown))}",
                status_code=422,
            )
        active_fields = parsed
    cutoff: str | None = None
    if min_purchase_order_no:
        cutoff = min_purchase_order_no.strip()
        if len(cutoff) > 128:
            raise AppError("VALIDATION_ERROR", "申购单号起始值过长", status_code=422)
    rows = await purchase_request_repository.list_sync_targets(
        session,
        limit=limit,
        cursor=cursor,
        fields=active_fields,
        min_purchase_order_no=cutoff,
    )
    has_more = len(rows) > limit
    items = [
        PurchaseRecordSyncTargetRead(trace_no=trace_no, target_count=count, cursor_id=cursor_id)
        for trace_no, count, cursor_id in rows[:limit]
    ]
    next_cursor = items[-1].cursor_id if items else 0
    return PurchaseRecordSyncTargetsRead(items=items, has_more=has_more, next_cursor=next_cursor)


async def apply_trace_sync(
    session: AsyncSession, trace_no: str, data: PurchaseRecordSyncTraceUpdate
) -> PurchaseRecordSyncResultRead:
    trace = trace_no.strip()
    if not trace:
        raise AppError("VALIDATION_ERROR", "追溯号不能为空", status_code=422)
    lines = list(
        (
            await session.scalars(
                select(PurchaseRequestLine)
                .where(PurchaseRequestLine.trace_no == trace)
                .order_by(PurchaseRequestLine.id)
                .with_for_update()
            )
        )
        .unique()
        .all()
    )
    if not lines:
        raise not_found("该追溯号的申购记录")

    request_ids = {line.purchase_request_id for line in lines}
    requests = list(
        (
            await session.scalars(
                select(PurchaseRequest)
                .where(PurchaseRequest.id.in_(request_ids))
                .with_for_update()
            )
        )
        .unique()
        .all()
    )

    affected_headers = 0
    for request in requests:
        changed = False
        for field in ("contract_no", "vessel_no", "consolidation_port"):
            value = getattr(data, field)
            if value is None or _is_blank(value) or not _is_blank(getattr(request, field)):
                continue
            setattr(request, field, value.strip())
            changed = True
        for field in ("consolidation_date", "sailing_date"):
            value = getattr(data, field)
            if value is None or getattr(request, field) is not None:
                continue
            setattr(request, field, value)
            changed = True
        if changed:
            request.version += 1
            affected_headers += 1

    affected_lines = 0
    for line in lines:
        changed = False
        if (
            data.salesperson is not None
            and not _is_blank(data.salesperson)
            and _is_blank(line.salesperson)
        ):
            line.salesperson = data.salesperson.strip()
            changed = True
        if (
            data.status is not None
            and not _is_blank(data.status)
            and line.status != data.status.strip()
            and line.status in _STATUS_PROGRESSION.get(data.status.strip(), set())
        ):
            line.status = data.status.strip()
            changed = True
        if changed:
            line.version += 1
            affected_lines += 1

    await session.flush()
    return PurchaseRecordSyncResultRead(
        affected_headers=affected_headers, affected_lines=affected_lines
    )
