from __future__ import annotations

import base64
import hashlib
import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement, SQLColumnExpression

from app.core.config import settings
from app.core.errors import AppError, version_conflict
from app.domain.enums import SourceType
from app.models import BusinessEventLog, FileObject, StockOperation
from app.schemas import FileObjectRead, Page

SearchableColumn = SQLColumnExpression[Any]


def fernet() -> Fernet:
    """用于加密敏感配置的 Fernet 实例。

    优先使用独立的 APP_FERNET_KEY；未配置时回退到由 jwt_secret 派生的密钥
    （两者都经 SHA-256 固定为 32 字节），保证既有已加密数据可继续解密。
    """
    if settings.fernet_key:
        digest = hashlib.sha256(settings.fernet_key.encode("utf-8")).digest()
    else:
        digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def operation_source_type(item: StockOperation) -> SourceType:
    """业务读路径的来源判定：MAIN_PROGRAM 来源的流水在落库时存 MANUAL，
    以 mini_program_user_name_snapshot 非空作为小程序来源的唯一判据。
    """
    if item.mini_program_user_name_snapshot is not None:
        return SourceType.MINI_PROGRAM
    return item.source_type


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


def split_or_search_terms(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    terms = (part.strip() for part in re.split(r"[|｜]", value))
    return tuple(dict.fromkeys(term for term in terms if term))


def contains_any(
    columns: Sequence[SearchableColumn], value: str | None
) -> ColumnElement[bool] | None:
    terms = split_or_search_terms(value)
    if not terms:
        return None
    return or_(*(column.contains(term, autoescape=True) for term in terms for column in columns))


def identity_hash(name: str, model_spec: str, unit_name: str) -> str:
    raw = (
        f"{normalized_text(name)}\0{normalized_text(model_spec)}\0{normalized_text(unit_name)}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_version(expected: int | None, actual: int) -> None:
    if expected is not None and expected != actual:
        raise version_conflict(expected, actual)


def validate_quantity_precision(quantity: Decimal) -> None:
    raw_exponent = quantity.normalize().as_tuple().exponent
    exponent = -raw_exponent if isinstance(raw_exponent, int) else 0
    if exponent > 1:
        raise AppError(
            "INVALID_QUANTITY_PRECISION",
            "数量最多保留 1 位小数",
            details={"quantity": str(quantity), "decimal_places": 1},
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
        mime_type=file.mime_type,
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
        occurred_at=utcnow(),
        remark=remark,
        before_data=before_data,
        after_data=after_data,
    )
    session.add(event)
    await session.flush()
    return event
