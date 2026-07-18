from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.core.security import hash_password
from app.models import MeasurementUnit, ProjectSubitem, User
from app.schemas import (
    MeasurementUnitCreate,
    MeasurementUnitUpdate,
    ProjectSubitemCreate,
    ProjectSubitemUpdate,
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


async def create_unit(
    session: AsyncSession, data: MeasurementUnitCreate, user_id: int
) -> MeasurementUnit:
    item = MeasurementUnit(**data.model_dump(), created_by=user_id, updated_by=user_id)
    session.add(item)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError("DUPLICATE_DICTIONARY", "计量单位编码或名称已存在", status_code=409) from exc
    return item


async def update_unit(
    session: AsyncSession, item_id: int, data: MeasurementUnitUpdate, user_id: int
) -> MeasurementUnit:
    item = await session.get(MeasurementUnit, item_id)
    if item is None:
        raise not_found("计量单位")
    validate_version(data.version, item.version)
    for key, value in data.model_dump(exclude={"version"}, exclude_none=True).items():
        setattr(item, key, value)
    item.updated_by = user_id
    item.version += 1
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError("DUPLICATE_DICTIONARY", "计量单位编码或名称已存在", status_code=409) from exc
    return item


async def list_projects(
    session: AsyncSession, keyword: str | None, enabled: bool | None, page: int, page_size: int
) -> tuple[list[ProjectSubitem], int]:
    query = select(ProjectSubitem)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            or_(
                ProjectSubitem.project_code.like(like),
                ProjectSubitem.project_name.like(like),
                ProjectSubitem.subitem_no.like(like),
                ProjectSubitem.subitem_name.like(like),
            )
        )
    if enabled is not None:
        query = query.where(ProjectSubitem.enabled == enabled)
    items, total = await _paged(session, query, ProjectSubitem, page, page_size)
    return items, total


async def create_project(
    session: AsyncSession, data: ProjectSubitemCreate, user_id: int
) -> ProjectSubitem:
    item = ProjectSubitem(**data.model_dump(), created_by=user_id, updated_by=user_id)
    session.add(item)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(
            "DUPLICATE_DICTIONARY", "项目编码和子项号组合已存在", status_code=409
        ) from exc
    return item


async def update_project(
    session: AsyncSession, item_id: int, data: ProjectSubitemUpdate, user_id: int
) -> ProjectSubitem:
    item = await session.get(ProjectSubitem, item_id)
    if item is None:
        raise not_found("项目子项")
    validate_version(data.version, item.version)
    for key, value in data.model_dump(exclude={"version"}, exclude_none=True).items():
        setattr(item, key, value)
    item.updated_by = user_id
    item.version += 1
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(
            "DUPLICATE_DICTIONARY", "项目编码和子项号组合已存在", status_code=409
        ) from exc
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
    for key in ("display_name", "role", "enabled"):
        value = getattr(data, key)
        if value is not None:
            setattr(item, key, value)
    if data.password:
        item.password_hash = hash_password(data.password)
    item.version += 1
    await session.flush()
    return item
