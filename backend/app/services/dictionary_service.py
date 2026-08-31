from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.core.security import decrypt_secret, encrypt_secret, hash_password
from app.models import User
from app.schemas import UserCreate, UserUpdate
from app.services.common import validate_version


def _hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_api_token(item: User) -> str:
    """生成新令牌：库中存哈希（认证查找）+ Fernet 密文（可逆回显），明文挂到对象上回显。"""
    token = str(uuid4())
    item.api_token_hash = _hash_api_token(token)
    item.api_token_enc = encrypt_secret(token)
    item.api_token = token
    return token


def _echo_api_token(item: User) -> None:
    """读取路径解密回显已保存的令牌（AGENTS.md「回显约定」）。

    兼容旧数据：升级前只有哈希、尚无密文的用户回显 None；其令牌下次成功用于
    接口调用时会在认证路径自动回写密文（见 core.permissions），此后持续回显。
    密钥轮换导致解密失败时同样降级为 None，不报错、不泄露。
    """
    item.api_token = decrypt_secret(item.api_token_enc)


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


async def list_users(
    session: AsyncSession, keyword: str | None, page: int, page_size: int
) -> tuple[list[User], int]:
    query = select(User)
    if keyword:
        query = query.where(
            or_(User.username.like(f"%{keyword}%"), User.display_name.like(f"%{keyword}%"))
        )
    items, total = await _paged(session, query, User, page, page_size)
    for item in items:
        _echo_api_token(item)
    return items, total


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    item = User(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
        enabled=data.enabled,
    )
    _issue_api_token(item)
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
    _echo_api_token(item)
    return item


async def regenerate_user_api_token(
    session: AsyncSession, item_id: int, version: int
) -> User:
    item = await session.get(User, item_id)
    if item is None:
        raise not_found("用户")
    validate_version(version, item.version)
    _issue_api_token(item)
    item.version += 1
    await session.flush()
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
