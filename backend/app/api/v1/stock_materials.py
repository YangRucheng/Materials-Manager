from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.permissions import CurrentUser, DbSession, WarehouseWriter
from app.schemas import (
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


async def _stock_read(session: DbSession, material_id: int) -> StockMaterialRead:
    item = await material_service.get_stock_material(session, material_id)
    operation_material_ids = await material_service.stock_material_ids_with_operations(
        session, [material_id]
    )
    return material_service.stock_read(
        item, has_operation_records=material_id in operation_material_ids
    )


@router.get("", response_model=Page[StockMaterialRead])
async def list_materials(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: str | None = None,
) -> Page[StockMaterialRead]:
    items, total = await material_service.search_stock_materials(
        session, keyword=keyword, page=page, page_size=page_size
    )
    operation_material_ids = await material_service.stock_material_ids_with_operations(
        session, [item.id for item in items]
    )
    return Page(
        items=[
            material_service.stock_read(
                item, has_operation_records=item.id in operation_material_ids
            )
            for item in items
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=StockMaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: StockMaterialCreate, session: DbSession, user: WarehouseWriter
) -> StockMaterialRead:
    item = await material_service.create_stock_material(session, data)
    return material_service.stock_read(item)


@router.get("/{material_id}", response_model=StockMaterialRead)
async def material_detail(
    material_id: int, session: DbSession, user: CurrentUser
) -> StockMaterialRead:
    return await _stock_read(session, material_id)


@router.patch("/{material_id}", response_model=StockMaterialRead)
async def update_material(
    material_id: int,
    data: StockMaterialUpdate,
    session: DbSession,
    user: WarehouseWriter,
) -> StockMaterialRead:
    item = await material_service.get_stock_material(session, material_id)
    await material_service.update_stock_material(session, item, data)
    return await _stock_read(session, material_id)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: int,
    version: int,
    session: DbSession,
    user: WarehouseWriter,
) -> None:
    item = await material_service.get_stock_material(session, material_id)
    await material_service.delete_stock_material(session, item, version)


@router.put("/{material_id}/replenishment-policy", response_model=StockMaterialRead)
async def save_policy(
    material_id: int,
    data: ReplenishmentPolicyWrite,
    session: DbSession,
    user: WarehouseWriter,
) -> StockMaterialRead:
    item = await material_service.get_stock_material(session, material_id)
    await replenishment_service.set_policy(session, item, data)
    return await _stock_read(session, material_id)
