from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.core.security import hash_password
from app.models import MeasurementUnit, User
from app.schemas import (
    MeasurementUnitCreate,
    MeasurementUnitUpdate,
    UserCreate,
    UserUpdate,
)
from app.services.common import validate_version


async def _paged(
    session: AsyncSession,
    query: Select[tuple[Any]],
    model: Any,
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    items = list(
        (
            await session.scalars(
                query.order_by(model.id).offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
    )
    return items, total


async def list_units(
    session: AsyncSession, keyword: str | None, enabled: bool | None, page: int, page_size: int
) -> tuple[list[MeasurementUnit], int]:
    query = select(MeasurementUnit)
    if keyword:
        query = query.where(
            or_(
                MeasurementUnit.code.like(f"%{keyword}%"), MeasurementUnit.name.like(f"%{keyword}%")
            )
        )
    if enabled is not None:
        query = query.where(MeasurementUnit.enabled == enabled)
    items, total = await _paged(session, query, MeasurementUnit, page, page_size)
    return items, total


async def create_unit(session: AsyncSession, data: MeasurementUnitCreate) -> MeasurementUnit:
    item = MeasurementUnit(**data.model_dump())
    session.add(item)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError("DUPLICATE_DICTIONARY", "计量单位编码或名称已存在", status_code=409) from exc
    return item


async def update_unit(
    session: AsyncSession, item_id: int, data: MeasurementUnitUpdate
) -> MeasurementUnit:
    item = await session.get(MeasurementUnit, item_id)
    if item is None:
        raise not_found("计量单位")
    validate_version(data.version, item.version)
    for key, value in data.model_dump(exclude={"version"}, exclude_none=True).items():
        setattr(item, key, value)
    item.version += 1
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError("DUPLICATE_DICTIONARY", "计量单位编码或名称已存在", status_code=409) from exc
    return item


async def list_users(
    session: AsyncSession, keyword: str | None, page: int, page_size: int
) -> tuple[list[User], int]:
    query = select(User)
    if keyword:
        query = query.where(
            or_(User.username.like(f"%{keyword}%"), User.display_name.like(f"%{keyword}%"))
        )
    items, total = await _paged(session, query, User, page, page_size)
    return items, total


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    item = User(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
        enabled=data.enabled,
    )
    session.add(item)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError("DUPLICATE_USERNAME", "用户名已存在", status_code=409) from exc
    return item


async def update_user(session: AsyncSession, item_id: int, data: UserUpdate) -> User:
    item = await session.get(User, item_id)
    if item is None:
        raise not_found("用户")
    validate_version(data.version, item.version)
    for key in ("username", "display_name", "role", "enabled"):
        value = getattr(data, key)
        if value is not None:
            setattr(item, key, value)
    if data.password:
        item.password_hash = hash_password(data.password)
    item.version += 1
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError("DUPLICATE_USERNAME", "用户名已存在", status_code=409) from exc
    return item


async def delete_user(session: AsyncSession, item_id: int, current_user_id: int) -> None:
    item = await session.get(User, item_id)
    if item is None:
        raise not_found("用户")
    if item.id == current_user_id:
        raise AppError(
            "CANNOT_DELETE_CURRENT_USER", "不能删除当前登录用户", status_code=409
        )
    await session.delete(item)
    await session.flush()
