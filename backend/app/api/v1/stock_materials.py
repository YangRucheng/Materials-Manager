from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.permissions import CurrentUser, DbSession, WarehouseWriter
from app.schemas import (
    ActionVersion,
    Page,
    ReplenishmentPolicyWrite,
    StockMaterialCreate,
    StockMaterialRead,
    StockMaterialUpdate,
)
from app.services import material_service, replenishment_service

router = APIRouter(prefix="/stock-materials", tags=["二级库物资"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]


@router.get("", response_model=Page[StockMaterialRead])
async def list_materials(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: str | None = None,
    enabled: bool | None = None,
) -> Page[StockMaterialRead]:
    items, total = await material_service.search_stock_materials(
        session, keyword=keyword, enabled=enabled, page=page, page_size=page_size
    )
    return Page(
        items=[material_service.stock_read(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=StockMaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: StockMaterialCreate, session: DbSession, user: WarehouseWriter
) -> StockMaterialRead:
    item = await material_service.create_stock_material(session, data, user.id)
    return material_service.stock_read(item)


@router.get("/{material_id}", response_model=StockMaterialRead)
async def material_detail(
    material_id: int, session: DbSession, user: CurrentUser
) -> StockMaterialRead:
    return material_service.stock_read(
        await material_service.get_stock_material(session, material_id)
    )


@router.patch("/{material_id}", response_model=StockMaterialRead)
async def update_material(
    material_id: int,
    data: StockMaterialUpdate,
    session: DbSession,
    user: WarehouseWriter,
) -> StockMaterialRead:
    item = await material_service.get_stock_material(session, material_id)
    item = await material_service.update_stock_material(session, item, data, user.id)
    return material_service.stock_read(item)


@router.post("/{material_id}/disable", response_model=StockMaterialRead)
async def disable_material(
    material_id: int,
    session: DbSession,
    user: WarehouseWriter,
    data: ActionVersion | None = None,
) -> StockMaterialRead:
    item = await material_service.get_stock_material(session, material_id)
    if data:
        from app.services.common import validate_version

        validate_version(data.version, item.version)
    item.enabled = False
    item.updated_by = user.id
    item.version += 1
    await session.flush()
    return material_service.stock_read(item)


@router.put("/{material_id}/replenishment-policy", response_model=StockMaterialRead)
async def save_policy(
    material_id: int,
    data: ReplenishmentPolicyWrite,
    session: DbSession,
    user: WarehouseWriter,
) -> StockMaterialRead:
    item = await material_service.get_stock_material(session, material_id)
    item = await replenishment_service.set_policy(session, item, data, user.id)
    return material_service.stock_read(item)
