from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.errors import AppError
from app.core.permissions import CurrentUser, DbSession, WarehouseWriter
from app.domain.enums import OperationType, SourceType
from app.schemas import (
    DashboardSummaryRead,
    InventoryBalanceRead,
    OperationCreate,
    OperationUpdate,
    Page,
    ReplenishmentDraftCreate,
    ReplenishmentDraftRead,
    ReverseOperationRequest,
    StockOperationRead,
)
from app.services import dashboard_service, inventory_service, replenishment_service

router = APIRouter(tags=["库存"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]


def _query_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.isdigit():
            return datetime.fromtimestamp(int(value) / 1000, tz=UTC).replace(tzinfo=None)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise AppError("VALIDATION_ERROR", "日期筛选参数无效", status_code=422) from exc
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(UTC).replace(tzinfo=None)


@router.get("/inventory/balances", response_model=Page[InventoryBalanceRead])
async def balances(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: str | None = None,
    min_qty: Decimal | None = None,
    max_qty: Decimal | None = None,
    low_stock: bool = False,
) -> Page[InventoryBalanceRead]:
    items, total = await inventory_service.inventory_balances(
        session,
        keyword=keyword,
        minimum_qty=min_qty,
        maximum_qty=max_qty,
        low_stock_only=low_stock,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/inventory/low-stock", response_model=Page[InventoryBalanceRead])
async def low_stock(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: str | None = None,
) -> Page[InventoryBalanceRead]:
    items, total = await inventory_service.inventory_balances(
        session,
        keyword=keyword,
        minimum_qty=None,
        maximum_qty=None,
        low_stock_only=True,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.get("/inventory/balances/{material_id}", response_model=InventoryBalanceRead)
async def balance_detail(
    material_id: int, session: DbSession, user: CurrentUser
) -> InventoryBalanceRead:
    items, _ = await inventory_service.inventory_balances(
        session,
        keyword=None,
        minimum_qty=None,
        maximum_qty=None,
        low_stock_only=False,
        page=1,
        page_size=1,
        material_id=material_id,
    )
    if not items:
        raise AppError("NOT_FOUND", "库存物资不存在", status_code=404)
    return items[0]


@router.post(
    "/inventory/inbounds", response_model=StockOperationRead, status_code=status.HTTP_201_CREATED
)
async def inbound(
    data: OperationCreate, session: DbSession, user: WarehouseWriter
) -> StockOperationRead:
    item = await inventory_service.create_operation(session, data, OperationType.INBOUND, user.id)
    return await inventory_service.operation_read(session, item)


@router.post(
    "/inventory/outbounds", response_model=StockOperationRead, status_code=status.HTTP_201_CREATED
)
async def outbound(
    data: OperationCreate, session: DbSession, user: WarehouseWriter
) -> StockOperationRead:
    item = await inventory_service.create_operation(session, data, OperationType.OUTBOUND, user.id)
    return await inventory_service.operation_read(session, item)


@router.get("/inventory/operations", response_model=Page[StockOperationRead])
async def operations(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    operation_no: str | None = None,
    operation_type: OperationType | None = None,
    material_name: str | None = None,
    operator_name: str | None = None,
    purchase_request_no: str | None = None,
    source_type: SourceType | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
) -> Page[StockOperationRead]:
    start_time = _query_time(start_at)
    end_time = _query_time(end_at)
    if start_time and end_time and start_time > end_time:
        raise AppError("VALIDATION_ERROR", "开始时间不能晚于结束时间", status_code=422)
    items, total = await inventory_service.search_operations(
        session,
        operation_no=operation_no,
        operation_type=operation_type,
        material_name=material_name,
        operator_name=operator_name,
        purchase_request_no=purchase_request_no,
        source_type=source_type,
        start_at=start_time,
        end_at=end_time,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[await inventory_service.operation_read(session, item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/inventory/operations/{operation_id}", response_model=StockOperationRead)
async def operation_detail(
    operation_id: int, session: DbSession, user: CurrentUser
) -> StockOperationRead:
    return await inventory_service.operation_read(
        session, await inventory_service.get_operation(session, operation_id)
    )


@router.patch("/inventory/operations/{operation_id}", response_model=StockOperationRead)
async def edit_operation(
    operation_id: int,
    data: OperationUpdate,
    session: DbSession,
    user: WarehouseWriter,
) -> StockOperationRead:
    item = await inventory_service.get_operation(session, operation_id, for_update=True)
    item = await inventory_service.update_operation(session, item, data, user.id)
    return await inventory_service.operation_read(session, item)


@router.post("/inventory/operations/{operation_id}/reverse", response_model=StockOperationRead)
async def reverse_operation(
    operation_id: int,
    data: ReverseOperationRequest,
    session: DbSession,
    user: WarehouseWriter,
) -> StockOperationRead:
    original = await inventory_service.get_operation(session, operation_id, for_update=True)
    item = await inventory_service.reverse_operation(session, original, data, user.id)
    return await inventory_service.operation_read(session, item)


@router.post(
    "/inventory/low-stock/{material_id}/create-replenishment-draft",
    response_model=ReplenishmentDraftRead,
)
async def replenish(
    material_id: int,
    data: ReplenishmentDraftCreate,
    session: DbSession,
    user: WarehouseWriter,
) -> ReplenishmentDraftRead:
    return await replenishment_service.create_replenishment_draft(
        session, material_id, data, user.id
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryRead)
async def summary(session: DbSession, user: CurrentUser) -> DashboardSummaryRead:
    return await dashboard_service.dashboard_summary(session)
