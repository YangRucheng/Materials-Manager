from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import PageNo, PageSize
from app.core.permissions import CurrentUser, DbSession, IfMatchVersion, WarehouseWriter
from app.domain.enums import MiniProgramCodeEnv
from app.schemas import (
    Page,
    ReplenishmentPolicyWrite,
    StockMaterialCreate,
    StockMaterialRead,
    StockMaterialUpdate,
)
from app.services import (
    ai_search_service,
    material_service,
    mini_program_service,
    replenishment_service,
)

router = APIRouter(prefix="/stock-materials", tags=["二级库物资"])


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


@router.get(
    "/mini-program-codes/{material_uuid}",
    responses={200: {"content": {"image/png": {}}}},
    response_class=Response,
    name="material_mini_program_code",
)
async def material_mini_program_code(
    material_uuid: UUID,
    env: MiniProgramCodeEnv,
    appid: Annotated[str, Query(min_length=1, max_length=64)],
    session: DbSession,
    user: CurrentUser,
) -> Response:
    item = await material_service.get_stock_material_by_uuid(session, material_uuid)
    code = await mini_program_service.generate_unlimited_material_code(
        material_uuid, env, appid
    )
    return Response(
        content=code,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=31536000, s-maxage=31536000, immutable",
            "Content-Disposition": (
                f'inline; filename="material-{item.uuid}-{env}-mini-program-code.png"'
            ),
        },
    )


@router.get(
    "/{material_id}/mini-program-code",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def material_mini_program_code_redirect(
    material_id: int,
    request: Request,
    session: DbSession,
    user: CurrentUser,
) -> RedirectResponse:
    item = await material_service.get_stock_material(session, material_id)
    env = await ai_search_service.get_mini_program_code_env(session)
    app_id = await ai_search_service.get_mini_program_code_app_id(session)
    target_path = request.url_for("material_mini_program_code", material_uuid=item.uuid).path
    return RedirectResponse(
        url=f"{target_path}?{urlencode({'env': env.value, 'appid': app_id})}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Cache-Control": "no-store"},
    )


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
    session: DbSession,
    user: WarehouseWriter,
    if_match: IfMatchVersion,
) -> None:
    item = await material_service.get_stock_material(session, material_id)
    await material_service.delete_stock_material(session, item, if_match)


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
