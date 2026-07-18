from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.permissions import CurrentUser, DbSession, PurchaseWriter, WarehouseWriter
from app.domain.enums import PurchaseRequestStatus
from app.models import PurchaseRequest
from app.schemas import (
    ActionVersion,
    Page,
    PreparedInboundRead,
    PurchaseRecordRead,
    PurchaseRecordUpdate,
    PurchaseRequestCreate,
    PurchaseRequestRead,
    PurchaseRequestUpdate,
    ReasonAction,
    StockOperationRead,
)
from app.services import inventory_service
from app.services import purchase_request_service as service

router = APIRouter(tags=["申购记录"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
StatusFilter = Annotated[PurchaseRequestStatus | None, Query(alias="status")]


@router.get("/purchase-requests", response_model=Page[PurchaseRequestRead])
async def requests(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    request_status: StatusFilter = None,
    keyword: str | None = None,
) -> Page[PurchaseRequestRead]:
    items, total = await service.search_requests(
        session, status=request_status, keyword=keyword, page=page, page_size=page_size
    )
    return Page(
        items=[await service.request_read(session, item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/purchase-requests", response_model=PurchaseRequestRead, status_code=status.HTTP_201_CREATED
)
async def create(
    data: PurchaseRequestCreate, session: DbSession, user: PurchaseWriter
) -> PurchaseRequestRead:
    return await service.request_read(session, await service.create_request(session, data, user.id))


@router.get("/purchase-requests/{request_id}", response_model=PurchaseRequestRead)
async def detail(request_id: int, session: DbSession, user: CurrentUser) -> PurchaseRequestRead:
    return await service.request_read(session, await service.get_request(session, request_id))


@router.patch("/purchase-requests/{request_id}", response_model=PurchaseRequestRead)
async def update(
    request_id: int, data: PurchaseRequestUpdate, session: DbSession, user: PurchaseWriter
) -> PurchaseRequestRead:
    item = await service.get_request(session, request_id, for_update=True)
    return await service.request_read(
        session, await service.update_request(session, item, data, user.id)
    )


async def _locked(session: DbSession, request_id: int) -> PurchaseRequest:
    return await service.get_request(session, request_id, for_update=True)


@router.post("/purchase-requests/{request_id}/submit", response_model=PurchaseRequestRead)
async def submit(
    request_id: int, data: ActionVersion, session: DbSession, user: PurchaseWriter
) -> PurchaseRequestRead:
    item = await service.submit_request(session, await _locked(session, request_id), data, user.id)
    return await service.request_read(session, item)


@router.post("/purchase-requests/{request_id}/accept", response_model=PurchaseRequestRead)
async def accept(
    request_id: int, data: ActionVersion, session: DbSession, user: PurchaseWriter
) -> PurchaseRequestRead:
    item = await service.accept_request(session, await _locked(session, request_id), data, user.id)
    return await service.request_read(session, item)


@router.post("/purchase-requests/{request_id}/return", response_model=PurchaseRequestRead)
async def return_item(
    request_id: int, data: ReasonAction, session: DbSession, user: PurchaseWriter
) -> PurchaseRequestRead:
    item = await service.return_request(session, await _locked(session, request_id), data, user.id)
    return await service.request_read(session, item)


@router.post("/purchase-requests/{request_id}/cancel", response_model=PurchaseRequestRead)
async def cancel(
    request_id: int, data: ActionVersion, session: DbSession, user: PurchaseWriter
) -> PurchaseRequestRead:
    item = await service.cancel_request(session, await _locked(session, request_id), data, user.id)
    return await service.request_read(session, item)


@router.post("/purchase-requests/{request_id}/close", response_model=PurchaseRequestRead)
async def close(
    request_id: int, data: ReasonAction, session: DbSession, user: PurchaseWriter
) -> PurchaseRequestRead:
    item = await service.close_request(session, await _locked(session, request_id), data, user.id)
    return await service.request_read(session, item)


@router.get("/purchase-requests/{request_id}/receipts", response_model=list[StockOperationRead])
async def receipts(
    request_id: int, session: DbSession, user: CurrentUser
) -> list[StockOperationRead]:
    items = await service.receipt_operations(session, request_id)
    return [await inventory_service.operation_read(session, item) for item in items]


@router.post(
    "/purchase-request-lines/{line_id}/prepare-inbound", response_model=PreparedInboundRead
)
async def prepare_inbound(
    line_id: int, session: DbSession, user: WarehouseWriter
) -> PreparedInboundRead:
    return await service.prepare_inbound(session, line_id)


@router.get("/purchase-records", response_model=Page[PurchaseRecordRead])
async def purchase_records(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    record_status: StatusFilter = None,
    keyword: str | None = None,
) -> Page[PurchaseRecordRead]:
    items, total = await service.search_purchase_records(
        session, status=record_status, keyword=keyword, page=page, page_size=page_size
    )
    return Page(
        items=[service.purchase_record_read(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/purchase-records/{line_id}", response_model=PurchaseRecordRead)
async def purchase_record(
    line_id: int, session: DbSession, user: CurrentUser
) -> PurchaseRecordRead:
    return service.purchase_record_read(await service.get_purchase_record(session, line_id))


@router.patch("/purchase-records/{line_id}", response_model=PurchaseRecordRead)
async def edit_purchase_record(
    line_id: int,
    data: PurchaseRecordUpdate,
    session: DbSession,
    user: PurchaseWriter,
) -> PurchaseRecordRead:
    line = await service.get_purchase_record(session, line_id, for_update=True)
    line = await service.update_purchase_record(session, line, data, user.id)
    return service.purchase_record_read(line)
