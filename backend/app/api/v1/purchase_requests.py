from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.errors import AppError
from app.core.permissions import CurrentUser, DbSession, PurchaseWriter
from app.schemas import (
    Page,
    PurchaseRecordFilterOptions,
    PurchaseRecordRead,
    PurchaseRecordResultExportRequest,
    PurchaseRecordUpdate,
)
from app.services import ai_search_service, excel_export_service, material_service
from app.services import purchase_request_service as service

router = APIRouter(tags=["申购记录"])
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
StatusFilter = Annotated[str | None, Query(alias="status", max_length=128)]
OR_SEARCH_DESCRIPTION = "可使用 | 或 ｜ 分隔多个关键词，同一参数内匹配任意关键词"
OrSearch = Annotated[str | None, Query(description=OR_SEARCH_DESCRIPTION)]
OrSearch128 = Annotated[str | None, Query(max_length=128, description=OR_SEARCH_DESCRIPTION)]
OrSearch255 = Annotated[str | None, Query(max_length=255, description=OR_SEARCH_DESCRIPTION)]
RecordSearchField = Literal[
    "plan_no",
    "plan_date",
    "purchase_order_no",
    "trace_no",
    "contract_no",
    "vessel_no",
    "consolidation_date",
    "consolidation_port",
    "sailing_date",
    "category",
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
RESULT_EXPORT_LIMIT = 10_000
RECORD_RESULT_HEADERS = {
    "purchase_qty": "申购数量",
    "plan_date": "需求日期",
    "purchase_order_no": "申购单号",
    "trace_no": "追溯号",
    "contract_no": "合同号",
    "vessel_no": "船号",
    "consolidation_date": "集港日期",
    "consolidation_port": "集港港口",
    "sailing_date": "发船日期",
    "category": "类别",
    "demand_department": "需求部门",
    "material_name": "物资",
    "actual_demand_person": "实际需求人",
    "purchase_responsible": "申购负责人",
    "salesperson": "业务员",
    "status": "状态",
    "purchase_date": "申购日期",
}


def _excel_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=excel_export_service.XLSX_CONTENT_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


def _quantity_text(value: Decimal) -> str:
    return format(value, "f").rstrip("0").rstrip(".") or "0"


@router.get("/purchase-records", response_model=Page[PurchaseRecordRead])
async def purchase_records(
    session: DbSession,
    user: CurrentUser,
    page: PageNo = 1,
    page_size: PageSize = 20,
    record_status: StatusFilter = None,
    empty_status: bool = False,
    keyword: OrSearch = None,
    search_field: RecordSearchField | None = None,
    search_value: OrSearch255 = None,
    purchase_order_no: OrSearch255 = None,
    trace_no: OrSearch255 = None,
    category: Annotated[str | None, Query(max_length=64)] = None,
    name: OrSearch128 = None,
    model_spec: OrSearch255 = None,
    actual_demand_person: OrSearch128 = None,
    purchase_responsible: OrSearch128 = None,
    salesperson: OrSearch128 = None,
    ai_expand: bool = False,
) -> Page[PurchaseRecordRead]:
    if ai_expand:
        keyword = await ai_search_service.expand_search_value(session, keyword)
        name = await ai_search_service.expand_search_value(session, name)
        if search_field == "material_name":
            search_value = await ai_search_service.expand_search_value(session, search_value)
    items, total = await service.search_purchase_records(
        session,
        status=record_status,
        empty_status=empty_status,
        keyword=keyword,
        search_field=search_field,
        search_value=search_value,
        purchase_order_no=purchase_order_no,
        trace_no=trace_no,
        category=category,
        name=name,
        model_spec=model_spec,
        actual_demand_person=actual_demand_person,
        purchase_responsible=purchase_responsible,
        salesperson=salesperson,
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
    (
        actual_demand_persons,
        purchase_responsibles,
        subitem_nos,
        categories,
    ) = await material_service.purchase_filter_options(session, moved=True, status=None)
    return PurchaseRecordFilterOptions(
        actual_demand_persons=actual_demand_persons,
        purchase_responsibles=purchase_responsibles,
        subitem_nos=subitem_nos,
        categories=categories,
        salespersons=await service.purchase_salesperson_options(session),
        statuses=await service.purchase_status_options(session),
    )


@router.post("/purchase-records/export-results")
async def export_purchase_record_results(
    data: PurchaseRecordResultExportRequest,
    session: DbSession,
    user: CurrentUser,
) -> Response:
    items, total = await service.search_purchase_records(
        session,
        status=data.status,
        empty_status=data.empty_status,
        keyword=None,
        search_field=None,
        search_value=None,
        purchase_order_no=data.purchase_order_no,
        trace_no=data.trace_no,
        category=data.category,
        name=data.name,
        model_spec=data.model_spec,
        actual_demand_person=None,
        purchase_responsible=data.purchase_responsible,
        salesperson=data.salesperson,
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
    rows = []
    for item in items:
        record = service.purchase_record_read(item)
        material_details = [record.material_name]
        if record.material_code:
            material_details.append(f"物料编码：{record.material_code}")
        if record.model_spec:
            material_details.append(f"型号规格：{record.model_spec}")
        rows.append(
            {
                "purchase_qty": f"{_quantity_text(record.purchase_qty)} {record.unit_name}",
                "plan_date": record.plan_date,
                "purchase_order_no": record.purchase_order_no,
                "trace_no": record.trace_no,
                "contract_no": record.contract_no,
                "vessel_no": record.vessel_no,
                "consolidation_date": record.consolidation_date,
                "consolidation_port": record.consolidation_port,
                "sailing_date": record.sailing_date,
                "category": record.category,
                "demand_department": record.demand_department,
                "material_name": "\n".join(material_details),
                "actual_demand_person": record.actual_demand_person,
                "purchase_responsible": record.purchase_responsible,
                "salesperson": record.salesperson,
                "status": record.status,
                "purchase_date": record.purchase_date,
            }
        )
    columns = [(key, RECORD_RESULT_HEADERS[key]) for key in data.columns]
    return _excel_response(*excel_export_service.render_result_excel("申购记录导出", columns, rows))


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
