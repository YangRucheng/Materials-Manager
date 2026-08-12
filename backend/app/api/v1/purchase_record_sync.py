from fastapi import APIRouter, Query

from app.core.permissions import DbSession, PurchaseWriter
from app.schemas import (
    PurchaseRecordSyncResultRead,
    PurchaseRecordSyncTargetsRead,
    PurchaseRecordSyncTraceUpdate,
)
from app.services import purchase_record_sync_service as service

router = APIRouter(tags=["申购记录同步"])


@router.get("/purchase-record-sync/targets", response_model=PurchaseRecordSyncTargetsRead)
async def sync_targets(
    session: DbSession,
    user: PurchaseWriter,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: int = Query(default=0, ge=0),
    fields: str | None = Query(
        default=None,
        description="逗号分隔的需要补全的同步字段；省略表示全部字段",
    ),
    min_purchase_order_no: str | None = Query(
        default=None,
        max_length=128,
        description="只返回申购单号（purchase_order_no）>= 该值的记录（含该值）",
    ),
) -> PurchaseRecordSyncTargetsRead:
    return await service.list_sync_targets(
        session, limit=limit, cursor=cursor, fields=fields,
        min_purchase_order_no=min_purchase_order_no,
    )


@router.post(
    "/purchase-record-sync/trace/{trace_no}", response_model=PurchaseRecordSyncResultRead
)
async def sync_trace(
    trace_no: str,
    data: PurchaseRecordSyncTraceUpdate,
    session: DbSession,
    user: PurchaseWriter,
) -> PurchaseRecordSyncResultRead:
    return await service.apply_trace_sync(session, trace_no, data)
