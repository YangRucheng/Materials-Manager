from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SHANGHAI
from app.core.errors import AppError, not_found
from app.domain.enums import PurchasePlanStatus
from app.models import (
    FileObject,
    PurchaseMaterial,
    PurchaseMaterialImage,
    PurchaseRequest,
    PurchaseRequestLine,
    PurchaseRequestLineImage,
)
from app.repositories import purchase_request_repository
from app.schemas import (
    BatchMovePurchasePlansRequest,
    BatchUpdatePurchaseRecordsRequest,
    MovePurchasePlanRequest,
    PurchaseRecordRead,
    PurchaseRecordUpdate,
)
from app.services.common import file_read, utc_aware, validate_version
from app.services.material_service import next_purchase_plan_no


def default_purchase_order_no() -> str:
    now = datetime.now(SHANGHAI)
    return f"申购 {now.year}/{now.month}/{now.day}"


def purchase_record_read(line: PurchaseRequestLine) -> PurchaseRecordRead:
    request = line.request
    return PurchaseRecordRead(
        line_id=line.id,
        purchase_request_id=request.id,
        purchase_material_id=line.purchase_material_id,
        plan_no=line.plan_no_snapshot,
        plan_date=line.plan_date_snapshot,
        purchase_order_no=request.purchase_order_no,
        trace_no=line.trace_no,
        contract_no=request.contract_no,
        vessel_no=request.vessel_no,
        consolidation_date=request.consolidation_date,
        consolidation_port=request.consolidation_port,
        sailing_date=request.sailing_date,
        status=line.status,
        material_code=line.material_code_snapshot,
        category=line.category_snapshot,
        demand_department=line.demand_department_snapshot,
        material_name=line.material_name_snapshot,
        model_spec=line.model_spec_snapshot,
        unit_name=line.unit_name_snapshot,
        purchase_qty=line.purchase_qty,
        actual_demand_person=line.actual_demand_person_snapshot,
        purchase_responsible=line.purchase_responsible_snapshot,
        salesperson=line.salesperson,
        plan_remark=line.plan_remark_snapshot,
        record_remark=request.remark,
        usage=line.usage,
        subitem_no=line.subitem_no,
        images=[file_read(link.file) for link in line.images],
        stock_material_id=line.stock_material_id_snapshot,
        purchase_date=request.purchase_date,
        created_at=utc_aware(request.created_at),
        updated_at=utc_aware(max(request.updated_at, line.updated_at)),
        version=request.version,
    )


async def move_plan_to_record(
    session: AsyncSession,
    material_id: int,
    data: MovePurchasePlanRequest,
) -> PurchaseRequestLine:
    return (await move_plans_to_record(session, [material_id], data))[0]


async def batch_move_plans_to_record(
    session: AsyncSession,
    data: BatchMovePurchasePlansRequest,
) -> list[PurchaseRequestLine]:
    return await move_plans_to_record(session, data.material_ids, data)


async def move_plans_to_record(
    session: AsyncSession,
    material_ids: list[int],
    data: MovePurchasePlanRequest,
) -> list[PurchaseRequestLine]:
    ids = sorted(set(material_ids))
    materials = list(
        (
            await session.scalars(
                select(PurchaseMaterial)
                .where(PurchaseMaterial.id.in_(ids))
                .order_by(PurchaseMaterial.id)
                .with_for_update()
            )
        )
        .unique()
        .all()
    )
    if len(materials) != len(ids):
        raise not_found("申购计划")
    uncoded = [material.id for material in materials if not material.material_code]
    if uncoded:
        raise AppError(
            "MATERIAL_CODE_REQUIRED",
            "未编码物资不能转入申购记录",
            status_code=409,
            details={"material_ids": uncoded},
        )
    moved_ids = set(
        (
            await session.scalars(
                select(PurchaseRequestLine.purchase_material_id)
                .where(PurchaseRequestLine.purchase_material_id.in_(ids))
                .with_for_update()
            )
        ).all()
    )
    if moved_ids:
        raise AppError(
            "PLAN_ALREADY_MOVED",
            "部分申购计划已转入申购记录",
            status_code=409,
            details={"material_ids": sorted(moved_ids)},
        )
    request = PurchaseRequest(
        purchase_order_no=(
            data.purchase_order_no or None
            if "purchase_order_no" in data.model_fields_set
            else default_purchase_order_no()
        ),
        contract_no=data.contract_no or None,
        vessel_no=data.vessel_no or None,
        consolidation_date=data.consolidation_date,
        consolidation_port=data.consolidation_port or None,
        sailing_date=data.sailing_date,
        remark=data.record_remark,
        purchase_date=data.purchase_date,
        lines=[],
    )
    request.lines = [
        PurchaseRequestLine(
            purchase_material_id=material.id,
            purchase_material=material,
            plan_no_snapshot=material.plan_no,
            plan_date_snapshot=material.plan_date,
            material_code_snapshot=material.material_code,
            category_snapshot=material.category,
            demand_department_snapshot=material.demand_department,
            material_name_snapshot=material.name,
            model_spec_snapshot=material.model_spec,
            unit_name_snapshot=material.unit_name,
            actual_demand_person_snapshot=material.actual_demand_person,
            purchase_responsible_snapshot=material.purchase_responsible,
            plan_remark_snapshot=material.remark,
            stock_material_id_snapshot=material.stock_material_id,
            purchase_qty=material.planned_qty,
            status=data.status,
            usage=material.usage,
            subitem_no=material.subitem_no,
            trace_no=data.trace_no or None,
            salesperson=data.salesperson,
            images=_line_images([link.file for link in material.images]),
        )
        for material in materials
    ]
    session.add(request)
    await session.flush()
    return request.lines


async def get_purchase_record(
    session: AsyncSession, line_id: int, *, for_update: bool = False
) -> PurchaseRequestLine:
    line = await purchase_request_repository.get_purchase_record(
        session, line_id, for_update=for_update
    )
    if line is None:
        raise not_found("申购记录")
    return line


async def _files(session: AsyncSession, image_ids: list[str]) -> list[FileObject]:
    if not image_ids:
        return []
    files = list(
        (await session.scalars(select(FileObject).where(FileObject.id.in_(image_ids)))).all()
    )
    by_id = {item.id: item for item in files}
    missing = [item_id for item_id in image_ids if item_id not in by_id]
    if missing:
        raise AppError("INVALID_IMAGE_ID", "图片不存在", details={"file_ids": missing})
    return [by_id[item_id] for item_id in image_ids]


def _line_images(files: list[FileObject]) -> list[PurchaseRequestLineImage]:
    return [
        PurchaseRequestLineImage(file_id=file.id, file=file, sort_order=index)
        for index, file in enumerate(files)
    ]


async def update_purchase_record(
    session: AsyncSession,
    line: PurchaseRequestLine,
    data: PurchaseRecordUpdate,
) -> PurchaseRequestLine:
    request = line.request
    validate_version(data.version, request.version)
    files = await _files(session, data.image_ids)
    request.purchase_order_no = data.purchase_order_no or None
    line.trace_no = data.trace_no or None
    request.contract_no = data.contract_no or None
    request.vessel_no = data.vessel_no or None
    request.consolidation_date = data.consolidation_date
    request.consolidation_port = data.consolidation_port or None
    request.sailing_date = data.sailing_date
    request.purchase_date = data.purchase_date
    line.salesperson = data.salesperson
    request.remark = data.record_remark
    request.version += 1
    line.plan_date_snapshot = data.plan_date
    line.material_code_snapshot = data.material_code
    line.category_snapshot = data.category
    line.demand_department_snapshot = data.demand_department
    line.material_name_snapshot = data.material_name
    line.model_spec_snapshot = data.model_spec
    line.unit_name_snapshot = data.unit_name
    line.actual_demand_person_snapshot = data.actual_demand_person
    line.purchase_responsible_snapshot = data.purchase_responsible
    line.plan_remark_snapshot = data.plan_remark
    line.stock_material_id_snapshot = data.stock_material_id
    line.purchase_qty = data.purchase_qty
    line.status = data.status
    line.usage = data.usage
    line.subitem_no = data.subitem_no
    line.images = _line_images(files)
    line.version += 1
    await session.flush()
    return line


async def batch_update_purchase_records(
    session: AsyncSession, data: BatchUpdatePurchaseRecordsRequest
) -> list[PurchaseRequestLine]:
    line_ids = [reference.line_id for reference in data.records]
    lines = list(
        (
            await session.scalars(
                select(PurchaseRequestLine)
                .where(PurchaseRequestLine.id.in_(line_ids))
                .with_for_update()
            )
        )
        .unique()
        .all()
    )
    lines_by_id = {line.id: line for line in lines}
    if len(lines_by_id) != len(line_ids):
        raise not_found("申购记录")

    request_ids = {line.purchase_request_id for line in lines}
    requests = list(
        (
            await session.scalars(
                select(PurchaseRequest)
                .where(PurchaseRequest.id.in_(request_ids))
                .with_for_update()
            )
        )
        .unique()
        .all()
    )
    requests_by_id = {request.id: request for request in requests}

    for reference in data.records:
        line = lines_by_id[reference.line_id]
        validate_version(reference.version, requests_by_id[line.purchase_request_id].version)

    update_fields = data.model_fields_set - {"records"}
    request_field_map = {
        "purchase_order_no": "purchase_order_no",
        "contract_no": "contract_no",
        "vessel_no": "vessel_no",
        "consolidation_date": "consolidation_date",
        "consolidation_port": "consolidation_port",
        "sailing_date": "sailing_date",
        "purchase_date": "purchase_date",
        "record_remark": "remark",
    }
    request_update_fields = update_fields & request_field_map.keys()
    selected_requests = {
        requests_by_id[lines_by_id[item.line_id].purchase_request_id] for item in data.records
    }
    for request in selected_requests:
        for source_field in request_update_fields:
            value = getattr(data, source_field)
            if source_field in {
                "purchase_order_no",
                "contract_no",
                "vessel_no",
                "consolidation_port",
            }:
                value = value or None
            setattr(request, request_field_map[source_field], value)
        request.version += 1

    updated: list[PurchaseRequestLine] = []
    for reference in data.records:
        line = lines_by_id[reference.line_id]
        if "plan_date" in update_fields:
            assert data.plan_date is not None
            if data.plan_date != line.plan_date_snapshot:
                line.plan_no_snapshot = await next_purchase_plan_no(session, data.plan_date)
                line.plan_date_snapshot = data.plan_date
                line.version += 1
                # flush 让下一条 next_purchase_plan_no 能看到本行新快照号
                await session.flush()
        if "actual_demand_person" in update_fields:
            assert data.actual_demand_person is not None
            line.actual_demand_person_snapshot = data.actual_demand_person
            line.version += 1
        if "purchase_responsible" in update_fields:
            assert data.purchase_responsible is not None
            line.purchase_responsible_snapshot = data.purchase_responsible
            line.version += 1
        if "status" in update_fields:
            assert data.status is not None
            line.status = data.status
            line.version += 1
        if "trace_no" in update_fields:
            line.trace_no = data.trace_no or None
            line.version += 1
        if "salesperson" in update_fields:
            line.salesperson = data.salesperson
            line.version += 1
        updated.append(line)

    await session.flush()
    return updated


async def restore_purchase_record_to_plan(
    session: AsyncSession,
    line: PurchaseRequestLine,
    version: int | None,
) -> PurchaseMaterial:
    request = await session.scalar(
        select(PurchaseRequest)
        .where(PurchaseRequest.id == line.purchase_request_id)
        .with_for_update()
    )
    if request is None:
        raise not_found("申购记录")
    validate_version(version, request.version)

    material = line.purchase_material
    if material is None:
        # 原计划已被定时任务清理：从快照重建全新计划，保留原计划号。
        material = PurchaseMaterial(
            plan_no=line.plan_no_snapshot,
            plan_date=line.plan_date_snapshot,
            material_code=line.material_code_snapshot,
            category=line.category_snapshot,
            urgency="正常",
            demand_department=line.demand_department_snapshot,
            name=line.material_name_snapshot,
            model_spec=line.model_spec_snapshot,
            unit_name=line.unit_name_snapshot,
            actual_demand_person=line.actual_demand_person_snapshot,
            purchase_responsible=line.purchase_responsible_snapshot,
            planned_qty=line.purchase_qty,
            usage=line.usage,
            subitem_no=line.subitem_no,
            remark=line.plan_remark_snapshot,
            stock_material_id=line.stock_material_id_snapshot,
            status=PurchasePlanStatus.NORMAL,
            images=[
                PurchaseMaterialImage(
                    file_id=link.file_id, file=link.file, sort_order=link.sort_order
                )
                for link in line.images
            ],
        )
        session.add(material)
    else:
        material.status = PurchasePlanStatus.NORMAL
        material.version += 1

    other_line_id = await session.scalar(
        select(PurchaseRequestLine.id)
        .where(
            PurchaseRequestLine.purchase_request_id == request.id,
            PurchaseRequestLine.id != line.id,
        )
        .limit(1)
    )
    if other_line_id is None:
        await session.delete(request)
    else:
        request.version += 1
        await session.delete(line)
    await session.flush()
    return material


async def search_purchase_records(
    session: AsyncSession,
    *,
    status: str | None,
    empty_status: bool,
    keyword: str | None,
    search_field: str | None,
    search_value: str | None,
    purchase_order_no: str | None,
    trace_no: str | None,
    category: str | None,
    name: str | None,
    model_spec: str | None,
    actual_demand_person: str | None,
    purchase_responsible: str | None,
    salesperson: str | None,
    subitem_no: str | None,
    empty_subitem_no: bool,
    page: int,
    page_size: int,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> tuple[list[PurchaseRequestLine], int]:
    return await purchase_request_repository.search_purchase_records(
        session,
        status=status,
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
        subitem_no=subitem_no,
        empty_subitem_no=empty_subitem_no,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def purchase_salesperson_options(session: AsyncSession) -> list[str]:
    return await purchase_request_repository.purchase_salesperson_options(session)


async def purchase_status_options(session: AsyncSession) -> list[str]:
    return await purchase_request_repository.purchase_status_options(session)


async def purchase_record_filter_options(
    session: AsyncSession,
) -> tuple[list[str], list[str], list[str], list[str]]:
    return await purchase_request_repository.purchase_record_filter_options(session)
