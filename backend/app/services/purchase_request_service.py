from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, invalid_transition, not_found
from app.domain.enums import PurchaseRequestStatus
from app.models import (
    ProjectSubitem,
    PurchaseMaterial,
    PurchaseRequest,
    PurchaseRequestLine,
    StockOperation,
    StockOperationLine,
    User,
)
from app.schemas import (
    ActionVersion,
    MovePurchasePlanRequest,
    PreparedInboundRead,
    PurchaseRecordRead,
    PurchaseRecordUpdate,
    PurchaseRequestCreate,
    PurchaseRequestLineRead,
    PurchaseRequestLineWrite,
    PurchaseRequestRead,
    PurchaseRequestUpdate,
    ReasonAction,
)
from app.services.common import (
    event_reads,
    log_event,
    utc_aware,
    utcnow,
    validate_quantity_precision,
    validate_version,
)

ZERO = Decimal("0")
SHANGHAI = timezone(timedelta(hours=8))


def default_request_no() -> str:
    now = datetime.now(SHANGHAI)
    return f"申购记录-{now.year}年{now.month}月{now.day}日"


async def get_request(
    session: AsyncSession, request_id: int, *, for_update: bool = False
) -> PurchaseRequest:
    query = select(PurchaseRequest).where(PurchaseRequest.id == request_id)
    if for_update:
        query = query.with_for_update()
    item = await session.scalar(query)
    if item is None:
        raise not_found("请购单")
    return item


async def request_read(session: AsyncSession, item: PurchaseRequest) -> PurchaseRequestRead:
    applicant_name = await session.scalar(
        select(User.display_name).where(User.id == item.applicant_id)
    )
    handler_name = (
        await session.scalar(select(User.display_name).where(User.id == item.handler_id))
        if item.handler_id
        else None
    )
    return PurchaseRequestRead(
        id=item.id,
        request_no=item.request_no,
        status=item.status,
        applicant_name=applicant_name or "未知用户",
        handler_name=handler_name,
        salesperson=item.salesperson,
        remark=item.remark,
        return_reason=item.return_reason,
        close_reason=item.close_reason,
        submitted_at=utc_aware(item.submitted_at),
        completed_at=utc_aware(item.completed_at),
        created_at=utc_aware(item.created_at),
        version=item.version,
        lines=[
            PurchaseRequestLineRead(
                id=line.id,
                purchase_material_id=line.purchase_material_id,
                material_code_snapshot=line.material_code_snapshot,
                material_name_snapshot=line.material_name_snapshot,
                model_spec_snapshot=line.model_spec_snapshot,
                unit_name_snapshot=line.unit_name_snapshot,
                requested_qty=line.requested_qty,
                received_qty=line.received_qty,
                usage=line.usage,
                project_subitem_id=line.project_subitem_id,
                project_code_snapshot=line.project_code_snapshot,
                subitem_no_snapshot=line.subitem_no_snapshot,
                subitem_name_snapshot=line.subitem_name_snapshot,
            )
            for line in item.lines
        ],
        events=await event_reads(session, "PURCHASE_REQUEST", item.id),
    )


def _merge_lines(lines: list[PurchaseRequestLineWrite]) -> list[PurchaseRequestLineWrite]:
    grouped: dict[tuple[int, int, str], PurchaseRequestLineWrite] = {}
    for line in lines:
        key = (line.purchase_material_id, line.project_subitem_id, line.usage)
        if key in grouped:
            existing = grouped[key]
            grouped[key] = PurchaseRequestLineWrite(
                purchase_material_id=existing.purchase_material_id,
                project_subitem_id=existing.project_subitem_id,
                usage=existing.usage,
                requested_qty=existing.requested_qty + line.requested_qty,
            )
        else:
            grouped[key] = line
    return list(grouped.values())


async def _replace_lines(
    session: AsyncSession,
    request: PurchaseRequest,
    lines: list[PurchaseRequestLineWrite],
    user_id: int,
) -> int | None:
    merged = _merge_lines(lines)
    material_ids = sorted({line.purchase_material_id for line in merged})
    project_ids = sorted({line.project_subitem_id for line in merged})
    materials = (
        list(
            (
                await session.scalars(
                    select(PurchaseMaterial).where(PurchaseMaterial.id.in_(material_ids))
                )
            )
            .unique()
            .all()
        )
        if material_ids
        else []
    )
    projects = (
        list(
            (
                await session.scalars(
                    select(ProjectSubitem).where(ProjectSubitem.id.in_(project_ids))
                )
            ).all()
        )
        if project_ids
        else []
    )
    material_map = {item.id: item for item in materials}
    project_map = {item.id: item for item in projects}
    if len(material_map) != len(material_ids):
        raise not_found("申购物资")
    if len(project_map) != len(project_ids):
        raise not_found("项目子项")
    responsible_names = {item.purchase_responsible for item in materials}
    if len(responsible_names) > 1:
        raise AppError(
            "MULTIPLE_PURCHASE_RESPONSIBLES",
            "同一请购单只能包含同一申购负责人的计划",
            status_code=409,
            details={"purchase_responsibles": sorted(responsible_names)},
        )
    for line in merged:
        material = material_map[line.purchase_material_id]
        project = project_map[line.project_subitem_id]
        if not material.enabled or not project.enabled:
            raise AppError("DISABLED_REFERENCE", "申购物资或项目子项已停用")
        validate_quantity_precision(line.requested_qty, material.unit.decimal_places)

    for old_line in list(request.lines):
        await session.delete(old_line)
    await session.flush()
    request.lines = [
        PurchaseRequestLine(
            purchase_material_id=line.purchase_material_id,
            material_code_snapshot=material_map[line.purchase_material_id].material_code,
            material_name_snapshot=material_map[line.purchase_material_id].name,
            model_spec_snapshot=material_map[line.purchase_material_id].model_spec,
            unit_name_snapshot=material_map[line.purchase_material_id].unit.name,
            requested_qty=line.requested_qty,
            received_qty=ZERO,
            usage=line.usage,
            project_subitem_id=line.project_subitem_id,
            project_code_snapshot=project_map[line.project_subitem_id].project_code,
            subitem_no_snapshot=project_map[line.project_subitem_id].subitem_no,
            subitem_name_snapshot=project_map[line.project_subitem_id].subitem_name,
            created_by=user_id,
            updated_by=user_id,
        )
        for line in merged
    ]
    return None


async def create_request(
    session: AsyncSession, data: PurchaseRequestCreate, user_id: int
) -> PurchaseRequest:
    item = PurchaseRequest(
        request_no=data.request_no or default_request_no(),
        status=PurchaseRequestStatus.DRAFT,
        applicant_id=user_id,
        remark=data.remark,
        created_by=user_id,
        updated_by=user_id,
        lines=[],
    )
    session.add(item)
    await session.flush()
    await _replace_lines(session, item, data.lines, user_id)
    await session.flush()
    await log_event(
        session,
        business_type="PURCHASE_REQUEST",
        business_id=item.id,
        action="CREATED",
        user_id=user_id,
        new_status=PurchaseRequestStatus.DRAFT.value,
    )
    return item


async def update_request(
    session: AsyncSession, item: PurchaseRequest, data: PurchaseRequestUpdate, user_id: int
) -> PurchaseRequest:
    validate_version(data.version, item.version)
    if item.status not in {PurchaseRequestStatus.DRAFT, PurchaseRequestStatus.RETURNED}:
        raise invalid_transition(item.status.value, "update")
    if any(line.received_qty > ZERO for line in item.lines):
        raise AppError("REQUEST_HAS_RECEIPTS", "已有到货记录的请购单不能修改", status_code=409)
    if data.request_no:
        item.request_no = data.request_no
    item.remark = data.remark
    item.updated_by = user_id
    item.version += 1
    await _replace_lines(session, item, data.lines, user_id)
    await session.flush()
    await log_event(
        session,
        business_type="PURCHASE_REQUEST",
        business_id=item.id,
        action="UPDATED",
        user_id=user_id,
    )
    return item


async def submit_request(
    session: AsyncSession, item: PurchaseRequest, data: ActionVersion, user_id: int
) -> PurchaseRequest:
    validate_version(data.version, item.version)
    if item.status not in {PurchaseRequestStatus.DRAFT, PurchaseRequestStatus.RETURNED}:
        raise invalid_transition(item.status.value, "submit")
    if not item.lines:
        raise AppError("EMPTY_PURCHASE_REQUEST", "请购单至少需要一条明细")
    missing: list[dict[str, int]] = []
    for index, line in enumerate(item.lines, start=1):
        material = line.purchase_material
        if not material.material_code:
            missing.append(
                {
                    "line_no": index,
                    "line_id": line.id,
                    "purchase_material_id": line.purchase_material_id,
                }
            )
        else:
            line.material_code_snapshot = material.material_code
            line.material_name_snapshot = material.name
            line.model_spec_snapshot = material.model_spec
            line.unit_name_snapshot = material.unit.name
    if missing:
        raise AppError(
            "MATERIAL_CODE_REQUIRED",
            "请购明细存在无编码物资",
            status_code=409,
            details={"lines": missing},
        )
    old = item.status
    item.status = PurchaseRequestStatus.SUBMITTED
    item.submitted_at = utcnow()
    item.return_reason = None
    item.updated_by = user_id
    item.version += 1
    await log_event(
        session,
        business_type="PURCHASE_REQUEST",
        business_id=item.id,
        action="SUBMITTED",
        user_id=user_id,
        old_status=old.value,
        new_status=item.status.value,
    )
    return item


async def accept_request(
    session: AsyncSession, item: PurchaseRequest, data: ActionVersion, user_id: int
) -> PurchaseRequest:
    validate_version(data.version, item.version)
    if item.status != PurchaseRequestStatus.SUBMITTED:
        raise invalid_transition(item.status.value, "accept")
    old = item.status
    item.status = PurchaseRequestStatus.PROCESSING
    item.handler_id = user_id
    item.updated_by = user_id
    item.version += 1
    await log_event(
        session,
        business_type="PURCHASE_REQUEST",
        business_id=item.id,
        action="ACCEPTED",
        user_id=user_id,
        old_status=old.value,
        new_status=item.status.value,
    )
    return item


async def return_request(
    session: AsyncSession, item: PurchaseRequest, data: ReasonAction, user_id: int
) -> PurchaseRequest:
    validate_version(data.version, item.version)
    if item.status not in {PurchaseRequestStatus.SUBMITTED, PurchaseRequestStatus.PROCESSING}:
        raise invalid_transition(item.status.value, "return")
    if any(line.received_qty > ZERO for line in item.lines):
        raise AppError("REQUEST_HAS_RECEIPTS", "已有到货记录的请购单不能退回", status_code=409)
    old = item.status
    item.status = PurchaseRequestStatus.RETURNED
    item.return_reason = data.reason
    item.updated_by = user_id
    item.version += 1
    await log_event(
        session,
        business_type="PURCHASE_REQUEST",
        business_id=item.id,
        action="RETURNED",
        user_id=user_id,
        old_status=old.value,
        new_status=item.status.value,
        remark=data.reason,
    )
    return item


async def cancel_request(
    session: AsyncSession, item: PurchaseRequest, data: ActionVersion, user_id: int
) -> PurchaseRequest:
    validate_version(data.version, item.version)
    if item.status not in {
        PurchaseRequestStatus.DRAFT,
        PurchaseRequestStatus.RETURNED,
        PurchaseRequestStatus.SUBMITTED,
        PurchaseRequestStatus.PROCESSING,
    }:
        raise invalid_transition(item.status.value, "cancel")
    if any(line.received_qty > ZERO for line in item.lines):
        raise AppError("REQUEST_HAS_RECEIPTS", "已有到货记录的请购单不能取消", status_code=409)
    old = item.status
    item.status = PurchaseRequestStatus.CANCELED
    item.updated_by = user_id
    item.version += 1
    await log_event(
        session,
        business_type="PURCHASE_REQUEST",
        business_id=item.id,
        action="CANCELED",
        user_id=user_id,
        old_status=old.value,
        new_status=item.status.value,
    )
    return item


async def close_request(
    session: AsyncSession, item: PurchaseRequest, data: ReasonAction, user_id: int
) -> PurchaseRequest:
    validate_version(data.version, item.version)
    if item.status not in {
        PurchaseRequestStatus.PROCESSING,
        PurchaseRequestStatus.PARTIALLY_RECEIVED,
    }:
        raise invalid_transition(item.status.value, "close")
    old = item.status
    item.status = PurchaseRequestStatus.CLOSED
    item.close_reason = data.reason
    item.completed_at = utcnow()
    item.updated_by = user_id
    item.version += 1
    await log_event(
        session,
        business_type="PURCHASE_REQUEST",
        business_id=item.id,
        action="CLOSED",
        user_id=user_id,
        old_status=old.value,
        new_status=item.status.value,
        remark=data.reason,
    )
    return item


async def prepare_inbound(session: AsyncSession, line_id: int) -> PreparedInboundRead:
    line = await session.scalar(
        select(PurchaseRequestLine).where(PurchaseRequestLine.id == line_id)
    )
    if line is None:
        raise not_found("申购记录明细")
    if line.request.status not in {
        PurchaseRequestStatus.SUBMITTED,
        PurchaseRequestStatus.PROCESSING,
        PurchaseRequestStatus.PARTIALLY_RECEIVED,
    }:
        raise AppError("INVALID_STATUS_TRANSITION", "当前申购记录状态不能发起入库", status_code=409)
    return PreparedInboundRead(
        purchase_request_no=line.request.request_no,
        line_id=line.id,
        purchase_material_id=line.purchase_material_id,
        material_name=line.material_name_snapshot,
        model_spec=line.model_spec_snapshot,
        unit_name=line.unit_name_snapshot,
        remaining_qty=line.requested_qty - line.received_qty,
        stock_material_id=line.purchase_material.stock_material_id,
    )


async def receipt_operations(session: AsyncSession, request_id: int) -> list[StockOperation]:
    await get_request(session, request_id)
    return list(
        (
            await session.scalars(
                select(StockOperation)
                .join(StockOperationLine)
                .join(PurchaseRequestLine)
                .where(PurchaseRequestLine.purchase_request_id == request_id)
                .order_by(StockOperation.occurred_at.desc())
            )
        )
        .unique()
        .all()
    )


async def search_requests(
    session: AsyncSession,
    *,
    status: PurchaseRequestStatus | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[PurchaseRequest], int]:
    query = select(PurchaseRequest)
    if status:
        query = query.where(PurchaseRequest.status == status)
    if keyword:
        query = query.where(
            PurchaseRequest.request_no.like(f"%{keyword}%")
            | PurchaseRequest.remark.like(f"%{keyword}%")
        )
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    items = list(
        (
            await session.scalars(
                query.order_by(PurchaseRequest.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return items, total


def purchase_record_read(line: PurchaseRequestLine) -> PurchaseRecordRead:
    request = line.request
    material = line.purchase_material
    return PurchaseRecordRead(
        line_id=line.id,
        purchase_request_id=request.id,
        purchase_material_id=line.purchase_material_id,
        request_no=request.request_no,
        status=request.status,
        material_code=line.material_code_snapshot or "",
        material_name=line.material_name_snapshot,
        model_spec=line.model_spec_snapshot,
        unit_name=line.unit_name_snapshot,
        planned_qty=line.requested_qty,
        received_qty=line.received_qty,
        remaining_qty=line.requested_qty - line.received_qty,
        actual_demand_person=material.actual_demand_person,
        purchase_responsible=material.purchase_responsible,
        salesperson=request.salesperson,
        remark=request.remark,
        usage=line.usage,
        project_subitem_name=(
            f"{line.project_code_snapshot} / {line.subitem_no_snapshot} "
            f"{line.subitem_name_snapshot}"
        ),
        stock_material_id=material.stock_material_id,
        submitted_at=utc_aware(request.submitted_at),
        created_at=utc_aware(request.created_at),
        version=request.version,
    )


async def move_plan_to_record(
    session: AsyncSession,
    material_id: int,
    data: MovePurchasePlanRequest,
    user_id: int,
) -> PurchaseRequestLine:
    material = await session.scalar(
        select(PurchaseMaterial).where(PurchaseMaterial.id == material_id).with_for_update()
    )
    if material is None:
        raise not_found("申购计划")
    if not material.material_code:
        raise AppError("MATERIAL_CODE_REQUIRED", "物资编码完成后才能转入申购记录", status_code=409)
    if material.project_subitem is None or not material.project_subitem.enabled:
        raise AppError("PROJECT_SUBITEM_REQUIRED", "请先为申购计划选择有效的项目子项")
    existing = await session.scalar(
        select(PurchaseRequestLine)
        .where(PurchaseRequestLine.purchase_material_id == material.id)
        .limit(1)
        .with_for_update()
    )
    if existing is not None:
        raise AppError("PLAN_ALREADY_MOVED", "该申购计划已转入申购记录", status_code=409)
    project = material.project_subitem
    request = PurchaseRequest(
        request_no=data.request_no,
        status=PurchaseRequestStatus.PROCESSING,
        applicant_id=user_id,
        salesperson=data.salesperson,
        remark=data.remark,
        submitted_at=utcnow(),
        created_by=user_id,
        updated_by=user_id,
        lines=[],
    )
    line = PurchaseRequestLine(
        purchase_material_id=material.id,
        purchase_material=material,
        material_code_snapshot=material.material_code,
        material_name_snapshot=material.name,
        model_spec_snapshot=material.model_spec,
        unit_name_snapshot=material.unit.name,
        requested_qty=material.planned_qty,
        received_qty=ZERO,
        usage=material.usage,
        project_subitem_id=project.id,
        project_subitem=project,
        project_code_snapshot=project.project_code,
        subitem_no_snapshot=project.subitem_no,
        subitem_name_snapshot=project.subitem_name,
        created_by=user_id,
        updated_by=user_id,
    )
    request.lines = [line]
    session.add(request)
    await session.flush()
    await log_event(
        session,
        business_type="PURCHASE_REQUEST",
        business_id=request.id,
        action="MOVED_FROM_PLAN",
        user_id=user_id,
        new_status=request.status.value,
        remark=f"申购计划 #{material.id}",
    )
    return line


async def get_purchase_record(
    session: AsyncSession, line_id: int, *, for_update: bool = False
) -> PurchaseRequestLine:
    query = select(PurchaseRequestLine).where(PurchaseRequestLine.id == line_id)
    if for_update:
        query = query.with_for_update()
    line = await session.scalar(query)
    if line is None:
        raise not_found("申购记录")
    return line


async def update_purchase_record(
    session: AsyncSession,
    line: PurchaseRequestLine,
    data: PurchaseRecordUpdate,
    user_id: int,
) -> PurchaseRequestLine:
    request = line.request
    validate_version(data.version, request.version)
    if data.request_no is not None:
        request.request_no = data.request_no
    request.salesperson = data.salesperson
    request.remark = data.remark
    request.updated_by = user_id
    request.version += 1
    await session.flush()
    return line


async def search_purchase_records(
    session: AsyncSession,
    *,
    status: PurchaseRequestStatus | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[PurchaseRequestLine], int]:
    visible_statuses = {
        PurchaseRequestStatus.SUBMITTED,
        PurchaseRequestStatus.PROCESSING,
        PurchaseRequestStatus.PARTIALLY_RECEIVED,
        PurchaseRequestStatus.COMPLETED,
        PurchaseRequestStatus.CLOSED,
    }
    query = (
        select(PurchaseRequestLine)
        .join(PurchaseRequest)
        .join(PurchaseMaterial)
        .where(PurchaseRequest.status.in_(visible_statuses))
    )
    if status:
        query = query.where(PurchaseRequest.status == status)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            or_(
                PurchaseRequest.request_no.like(like),
                PurchaseRequest.salesperson.like(like),
                PurchaseRequest.remark.like(like),
                PurchaseRequestLine.material_code_snapshot.like(like),
                PurchaseRequestLine.material_name_snapshot.like(like),
                PurchaseRequestLine.model_spec_snapshot.like(like),
            )
        )
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    items = list(
        (
            await session.scalars(
                query.order_by(PurchaseRequestLine.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return items, total
