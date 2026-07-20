from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, version_conflict
from app.models import BusinessEventLog, FileObject, User
from app.schemas import BusinessEventRead, FileObjectRead, Page


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def utc_naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


def utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip()).casefold()


def identity_hash(name: str, model_spec: str, unit_id: int) -> str:
    raw = f"{normalized_text(name)}\0{normalized_text(model_spec)}\0{unit_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_version(expected: int | None, actual: int) -> None:
    if expected is not None and expected != actual:
        raise version_conflict(expected, actual)


def validate_quantity_precision(quantity: Decimal, decimal_places: int) -> None:
    decimal_places = min(decimal_places, 1)
    raw_exponent = quantity.normalize().as_tuple().exponent
    exponent = -raw_exponent if isinstance(raw_exponent, int) else 0
    if exponent > decimal_places:
        raise AppError(
            "INVALID_QUANTITY_PRECISION",
            "数量最多保留 1 位小数，且不能超过计量单位允许范围",
            details={"quantity": str(quantity), "decimal_places": decimal_places},
        )


async def paginate(
    session: AsyncSession, query: Select[tuple[object]], page: int, page_size: int
) -> tuple[list[object], int]:
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = int((await session.scalar(count_query)) or 0)
    result = await session.scalars(query.offset((page - 1) * page_size).limit(page_size))
    return list(result.unique().all()), total


def page_result(items: list[object], page: int, page_size: int, total: int) -> Page[object]:
    return Page(items=items, page=page, page_size=page_size, total=total)


def file_read(file: FileObject) -> FileObjectRead:
    return FileObjectRead(
        id=file.id,
        original_name=file.original_name,
        mime_type="image/png",
        size_bytes=file.size_bytes,
        width=file.width,
        height=file.height,
    )


async def log_event(
    session: AsyncSession,
    *,
    business_type: str,
    business_id: int,
    action: str,
    user_id: int,
    old_status: str | None = None,
    new_status: str | None = None,
    remark: str | None = None,
    before_data: dict[str, object] | None = None,
    after_data: dict[str, object] | None = None,
) -> BusinessEventLog:
    event = BusinessEventLog(
        business_type=business_type,
        business_id=business_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        operator_id=user_id,
        occurred_at=utcnow(),
        remark=remark,
        before_data=before_data,
        after_data=after_data,
    )
    session.add(event)
    await session.flush()
    return event


async def event_reads(
    session: AsyncSession, business_type: str, business_id: int
) -> list[BusinessEventRead]:
    rows = (
        await session.execute(
            select(BusinessEventLog, User.display_name)
            .join(User, User.id == BusinessEventLog.operator_id)
            .where(
                BusinessEventLog.business_type == business_type,
                BusinessEventLog.business_id == business_id,
            )
            .order_by(BusinessEventLog.id)
        )
    ).all()
    return [
        BusinessEventRead(
            id=event.id,
            action=event.action,
            old_status=event.old_status,
            new_status=event.new_status,
            operator_name=operator_name,
            occurred_at=utc_aware(event.occurred_at),
            remark=event.remark,
        )
        for event, operator_name in rows
    ]
