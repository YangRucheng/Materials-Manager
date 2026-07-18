from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.core.permissions import CurrentUser, DbSession, PurchaseWriter, require_roles
from app.domain.enums import Role
from app.models import User
from app.schemas import (
    BatchMovePurchasePlansRequest,
    LinkStockMaterialRequest,
    MovePurchasePlanRequest,
    Page,
    PurchaseMaterialCreate,
    PurchaseMaterialRead,
    PurchaseMaterialUpdate,
    PurchasePlanExportRequest,
    PurchaseRecordRead,
)
from app.services import excel_export_service, material_service, purchase_request_service
from app.services.common import validate_version

router = APIRouter(prefix="/purchase-materials", tags=["申购计划"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
LinkWriter = Annotated[
    User,
    Depends(require_roles(Role.SUPER_ADMIN, Role.WAREHOUSE_ADMIN, Role.PURCHASE_ADMIN)),
]


@router.get("", response_model=Page[PurchaseMaterialRead])
async def list_materials(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: str | None = None,
    enabled: bool | None = None,
    coded: bool | None = None,
    moved: bool | None = None,
) -> Page[PurchaseMaterialRead]:
    items, total = await material_service.search_purchase_materials(
        session,
        keyword=keyword,
        enabled=enabled,
        coded=coded,
        moved=moved,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[await material_service.purchase_read(session, item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=PurchaseMaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: PurchaseMaterialCreate, session: DbSession, user: PurchaseWriter
) -> PurchaseMaterialRead:
    item = await material_service.create_purchase_material(session, data, user.id)
    return await material_service.purchase_read(session, item)


def _excel_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=excel_export_service.XLSX_CONTENT_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/export-uncoded")
async def export_uncoded_materials(
    session: DbSession,
    user: CurrentUser,
    keyword: str | None = None,
) -> Response:
    materials = await material_service.purchase_materials_for_export(
        session, keyword=keyword, coded=False, moved=False
    )
    rows = [
        {
            "serial": index,
            "name": item.name,
            "model_spec": item.model_spec,
            "unit_name": item.unit.name,
            "actual_demand_person": item.actual_demand_person,
            "application_reason": "；".join(
                value for value in (item.usage, item.remark) if value
            ),
        }
        for index, item in enumerate(materials, start=1)
    ]
    return _excel_response(
        *excel_export_service.render_excel("material-code-application.json", rows)
    )


@router.post("/export-purchase-application")
async def export_purchase_application(
    data: PurchasePlanExportRequest,
    session: DbSession,
    user: CurrentUser,
) -> Response:
    materials = await material_service.purchase_materials_for_export(
        session, material_ids=data.material_ids, coded=True, moved=False
    )
    rows = [
        {
            "material_code": item.material_code,
            "name": item.name,
            "planned_qty": item.planned_qty,
            "actual_demand_person": item.actual_demand_person,
            "usage": item.usage,
            "remark": item.remark,
            "subitem_no": item.subitem_no,
        }
        for item in materials
    ]
    return _excel_response(*excel_export_service.render_excel("purchase-application.json", rows))


@router.post("/batch-move-to-record", response_model=list[PurchaseRecordRead])
async def batch_move_to_record(
    data: BatchMovePurchasePlansRequest,
    session: DbSession,
    user: PurchaseWriter,
) -> list[PurchaseRecordRead]:
    lines = await purchase_request_service.batch_move_plans_to_record(session, data, user.id)
    return [purchase_request_service.purchase_record_read(line) for line in lines]


@router.get("/{material_id}", response_model=PurchaseMaterialRead)
async def material_detail(
    material_id: int, session: DbSession, user: CurrentUser
) -> PurchaseMaterialRead:
    return await material_service.purchase_read(
        session, await material_service.get_purchase_material(session, material_id)
    )


@router.patch("/{material_id}", response_model=PurchaseMaterialRead)
async def update_material(
    material_id: int,
    data: PurchaseMaterialUpdate,
    session: DbSession,
    user: PurchaseWriter,
) -> PurchaseMaterialRead:
    item = await material_service.get_purchase_material(session, material_id)
    item = await material_service.update_purchase_material(session, item, data, user.id)
    return await material_service.purchase_read(session, item)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: int,
    version: int,
    session: DbSession,
    user: PurchaseWriter,
) -> None:
    item = await material_service.get_purchase_material(session, material_id)
    await material_service.delete_purchase_material(session, item, version)


@router.post("/{material_id}/link-stock-material", response_model=PurchaseMaterialRead)
async def link_stock_material(
    material_id: int,
    data: LinkStockMaterialRequest,
    session: DbSession,
    user: LinkWriter,
) -> PurchaseMaterialRead:
    item = await material_service.get_purchase_material(session, material_id)
    validate_version(data.version, item.version)
    stock = await material_service._validate_stock_link(session, data.stock_material_id)
    item.stock_material_id = data.stock_material_id
    item.stock_material = stock
    item.updated_by = user.id
    item.version += 1
    await session.flush()
    return await material_service.purchase_read(session, item)


@router.post("/{material_id}/move-to-record", response_model=PurchaseRecordRead)
async def move_to_record(
    material_id: int,
    data: MovePurchasePlanRequest,
    session: DbSession,
    user: PurchaseWriter,
) -> PurchaseRecordRead:
    line = await purchase_request_service.move_plan_to_record(session, material_id, data, user.id)
    return purchase_request_service.purchase_record_read(line)
