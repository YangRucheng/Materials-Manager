from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.core.errors import AppError
from app.core.permissions import CurrentUser, DbSession, PurchaseWriter, require_roles
from app.domain.enums import PurchasePlanStatus, Role
from app.models import User
from app.schemas import (
    ApiError,
    BatchMovePurchasePlansRequest,
    BatchUpdatePurchasePlansRequest,
    LinkStockMaterialRequest,
    MovePurchasePlanRequest,
    Page,
    PurchaseFilterOptions,
    PurchaseMaterialCreate,
    PurchaseMaterialRead,
    PurchaseMaterialUpdate,
    PurchasePlanExportRequest,
    PurchasePlanResultExportRequest,
    PurchaseRecordRead,
)
from app.services import (
    ai_search_service,
    excel_export_service,
    material_service,
    purchase_request_service,
)
from app.services.common import validate_version

router = APIRouter(prefix="/purchase-materials", tags=["申购计划"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
OR_SEARCH_DESCRIPTION = "可使用 | 或 ｜ 分隔多个关键词，同一参数内匹配任意关键词"
OrSearch = Annotated[str | None, Query(description=OR_SEARCH_DESCRIPTION)]
OrSearch128 = Annotated[str | None, Query(max_length=128, description=OR_SEARCH_DESCRIPTION)]
OrSearch255 = Annotated[str | None, Query(max_length=255, description=OR_SEARCH_DESCRIPTION)]
PlanSearchField = Literal[
    "plan_no",
    "plan_date",
    "material_code",
    "name",
    "model_spec",
    "unit_name",
    "planned_qty",
    "usage",
    "subitem_no",
    "remark",
]
LinkWriter = Annotated[
    User,
    Depends(require_roles(Role.SUPER_ADMIN, Role.WAREHOUSE_ADMIN, Role.PURCHASE_ADMIN)),
]
RESULT_EXPORT_LIMIT = 10_000
PLAN_RESULT_HEADERS = {
    "plan_no": "计划 ID",
    "plan_date": "需求日期",
    "material_code": "物料编码",
    "name": "名称",
    "model_spec": "型号规格",
    "planned_qty": "计划数量",
    "unit_name": "单位",
    "actual_demand_person": "实际需求人",
    "purchase_responsible": "申购负责人",
    "subitem_no": "子项号",
    "usage": "用途",
}


@router.get("", response_model=Page[PurchaseMaterialRead])
async def list_materials(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    keyword: OrSearch = None,
    search_field: PlanSearchField | None = None,
    search_value: OrSearch255 = None,
    name: OrSearch128 = None,
    model_spec: OrSearch255 = None,
    actual_demand_person: OrSearch128 = None,
    empty_actual_demand_person: bool = False,
    purchase_responsible: OrSearch128 = None,
    subitem_no: Annotated[str | None, Query(max_length=64)] = None,
    empty_subitem_no: bool = False,
    status: PurchasePlanStatus | None = None,
    enabled: bool | None = None,
    coded: bool | None = None,
    moved: bool | None = None,
    ai_expand: bool = False,
) -> Page[PurchaseMaterialRead]:
    if user.role != Role.SUPER_ADMIN:
        if status == PurchasePlanStatus.ARCHIVED:
            raise AppError(
                "ARCHIVED_PURCHASE_PLAN_FORBIDDEN",
                "仅超级管理员可查询已归档申购计划",
                status_code=403,
            )
        status = PurchasePlanStatus.NORMAL
    if ai_expand:
        keyword = await ai_search_service.expand_search_value(session, keyword)
        name = await ai_search_service.expand_search_value(session, name)
        if search_field == "name":
            search_value = await ai_search_service.expand_search_value(session, search_value)
    items, total = await material_service.search_purchase_materials(
        session,
        keyword=keyword,
        search_field=search_field,
        search_value=search_value,
        name=name,
        model_spec=model_spec,
        actual_demand_person=actual_demand_person,
        empty_actual_demand_person=empty_actual_demand_person,
        purchase_responsible=purchase_responsible,
        subitem_no=subitem_no,
        empty_subitem_no=empty_subitem_no,
        status=status,
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


@router.get("/filter-options", response_model=PurchaseFilterOptions)
async def filter_options(
    session: DbSession,
    user: CurrentUser,
    moved: bool | None = None,
) -> PurchaseFilterOptions:
    actual_demand_persons, purchase_responsibles, subitem_nos = (
        await material_service.purchase_filter_options(
            session,
            moved=moved,
            status=None if user.role == Role.SUPER_ADMIN else PurchasePlanStatus.NORMAL,
        )
    )
    return PurchaseFilterOptions(
        actual_demand_persons=actual_demand_persons,
        purchase_responsibles=purchase_responsibles,
        subitem_nos=subitem_nos,
    )


@router.post("", response_model=PurchaseMaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: PurchaseMaterialCreate, session: DbSession, user: PurchaseWriter
) -> PurchaseMaterialRead:
    item = await material_service.create_purchase_material(session, data)
    return await material_service.purchase_read(session, item)


def _excel_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=excel_export_service.XLSX_CONTENT_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/export-results")
async def export_material_results(
    data: PurchasePlanResultExportRequest,
    session: DbSession,
    user: CurrentUser,
) -> Response:
    export_status = data.status
    if user.role != Role.SUPER_ADMIN:
        if export_status == PurchasePlanStatus.ARCHIVED:
            raise AppError(
                "ARCHIVED_PURCHASE_PLAN_FORBIDDEN",
                "仅超级管理员可查询已归档申购计划",
                status_code=403,
            )
        export_status = PurchasePlanStatus.NORMAL
    items, total = await material_service.search_purchase_materials(
        session,
        keyword=None,
        search_field=None,
        search_value=None,
        name=data.name,
        model_spec=data.model_spec,
        actual_demand_person=data.actual_demand_person,
        empty_actual_demand_person=data.empty_actual_demand_person,
        purchase_responsible=None,
        subitem_no=data.subitem_no,
        empty_subitem_no=data.empty_subitem_no,
        status=export_status,
        enabled=None,
        coded=None,
        moved=False,
        page=1,
        page_size=RESULT_EXPORT_LIMIT + 1,
    )
    if total > RESULT_EXPORT_LIMIT:
        raise AppError(
            "EXPORT_RESULT_LIMIT_EXCEEDED",
            f"查询结果超过 {RESULT_EXPORT_LIMIT} 行，请缩小筛选范围后导出",
            status_code=400,
            details={"total": total, "limit": RESULT_EXPORT_LIMIT},
        )
    rows = [
        {
            "plan_no": item.plan_no,
            "plan_date": item.plan_date,
            "material_code": item.material_code,
            "name": item.name,
            "model_spec": item.model_spec,
            "planned_qty": item.planned_qty,
            "unit_name": item.unit.name,
            "actual_demand_person": item.actual_demand_person,
            "purchase_responsible": item.purchase_responsible,
            "subitem_no": item.subitem_no,
            "usage": item.usage,
        }
        for item in items
    ]
    columns = [(key, PLAN_RESULT_HEADERS[key]) for key in data.columns]
    return _excel_response(
        *excel_export_service.render_result_excel("申购计划导出", columns, rows)
    )


@router.get(
    "/export-uncoded",
    responses={400: {"model": ApiError, "description": "Excel 导出模板缺失或格式错误"}},
)
async def export_uncoded_materials(
    session: DbSession,
    user: CurrentUser,
    keyword: str | None = None,
) -> Response:
    materials = await material_service.purchase_materials_for_export(
        session,
        keyword=keyword,
        coded=False,
        moved=False,
        status=PurchasePlanStatus.NORMAL,
    )
    rows = [
        {
            "serial": index,
            "name": item.name,
            "model_spec": item.model_spec,
            "unit_name": item.unit.name,
            "actual_demand_person": item.actual_demand_person,
            "application_reason": "；".join(value for value in (item.usage, item.remark) if value),
        }
        for index, item in enumerate(materials, start=1)
    ]
    return _excel_response(
        *excel_export_service.render_excel("material-code-application.json", rows)
    )


@router.post(
    "/export-purchase-application",
    responses={400: {"model": ApiError, "description": "Excel 导出模板缺失或格式错误"}},
)
async def export_purchase_application(
    data: PurchasePlanExportRequest,
    session: DbSession,
    user: CurrentUser,
) -> Response:
    materials = await material_service.purchase_materials_for_export(
        session,
        material_ids=data.material_ids,
        coded=True,
        moved=False,
        status=None if user.role == Role.SUPER_ADMIN else PurchasePlanStatus.NORMAL,
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
    lines = await purchase_request_service.batch_move_plans_to_record(session, data)
    return [purchase_request_service.purchase_record_read(line) for line in lines]


@router.patch("/batch", response_model=list[PurchaseMaterialRead])
async def batch_update_materials(
    data: BatchUpdatePurchasePlansRequest,
    session: DbSession,
    user: PurchaseWriter,
) -> list[PurchaseMaterialRead]:
    items = await material_service.batch_update_purchase_materials(session, data)
    return [await material_service.purchase_read(session, item) for item in items]


@router.get("/{material_id}", response_model=PurchaseMaterialRead)
async def material_detail(
    material_id: int, session: DbSession, user: CurrentUser
) -> PurchaseMaterialRead:
    item = await material_service.get_purchase_material(session, material_id)
    if item.status == PurchasePlanStatus.ARCHIVED and user.role != Role.SUPER_ADMIN:
        raise AppError(
            "ARCHIVED_PURCHASE_PLAN_FORBIDDEN",
            "仅超级管理员可查询已归档申购计划",
            status_code=403,
        )
    return await material_service.purchase_read(session, item)


@router.patch("/{material_id}", response_model=PurchaseMaterialRead)
async def update_material(
    material_id: int,
    data: PurchaseMaterialUpdate,
    session: DbSession,
    user: PurchaseWriter,
) -> PurchaseMaterialRead:
    item = await material_service.get_purchase_material(session, material_id)
    item = await material_service.update_purchase_material(session, item, data)
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
    line = await purchase_request_service.move_plan_to_record(session, material_id, data)
    return purchase_request_service.purchase_record_read(line)
