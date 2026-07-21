from typing import Annotated

from fastapi import APIRouter, Query

from app.core.permissions import CurrentUser, DbSession, PurchaseWriter
from app.schemas import Page, PurchaseRecordRead, PurchaseRecordUpdate
from app.services import purchase_request_service as service

router = APIRouter(tags=["申购记录"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
StatusFilter = Annotated[str | None, Query(alias="status", max_length=128)]


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
    line = await service.update_purchase_record(session, line, data)
    return service.purchase_record_read(line)
