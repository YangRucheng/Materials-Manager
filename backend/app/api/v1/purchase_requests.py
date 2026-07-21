from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.permissions import CurrentUser, DbSession, PurchaseWriter
from app.schemas import (
    Page,
    PurchaseRecordFilterOptions,
    PurchaseRecordRead,
    PurchaseRecordUpdate,
)
from app.services import material_service
from app.services import purchase_request_service as service

router = APIRouter(tags=["申购记录"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
StatusFilter = Annotated[str | None, Query(alias="status", max_length=128)]
RecordSearchField = Literal[
    "plan_no",
    "plan_date",
    "purchase_order_no",
    "trace_no",
    "material_code",
    "material_name",
    "model_spec",
    "unit_name",
    "purchase_qty",
    "salesperson",
    "status",
    "purchase_date",
    "usage",
    "subitem_no",
    "plan_remark",
    "record_remark",
]


@router.get("/purchase-records", response_model=Page[PurchaseRecordRead])
async def purchase_records(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    record_status: StatusFilter = None,
    empty_status: bool = False,
    keyword: str | None = None,
    search_field: RecordSearchField | None = None,
    search_value: Annotated[str | None, Query(max_length=255)] = None,
    name: Annotated[str | None, Query(max_length=128)] = None,
    model_spec: Annotated[str | None, Query(max_length=255)] = None,
    actual_demand_person: Annotated[str | None, Query(max_length=128)] = None,
    purchase_responsible: Annotated[str | None, Query(max_length=128)] = None,
) -> Page[PurchaseRecordRead]:
    items, total = await service.search_purchase_records(
        session,
        status=record_status,
        empty_status=empty_status,
        keyword=keyword,
        search_field=search_field,
        search_value=search_value,
        name=name,
        model_spec=model_spec,
        actual_demand_person=actual_demand_person,
        purchase_responsible=purchase_responsible,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[service.purchase_record_read(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/purchase-records/filter-options", response_model=PurchaseRecordFilterOptions)
async def purchase_record_filter_options(
    session: DbSession, user: CurrentUser
) -> PurchaseRecordFilterOptions:
    actual_demand_persons, purchase_responsibles = (
        await material_service.purchase_filter_options(session, moved=True)
    )
    return PurchaseRecordFilterOptions(
        actual_demand_persons=actual_demand_persons,
        purchase_responsibles=purchase_responsibles,
        statuses=await service.purchase_status_options(session),
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
