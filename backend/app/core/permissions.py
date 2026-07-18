from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.domain.enums import Role
from app.models import User

bearer = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise AppError("UNAUTHORIZED", "请先登录", status_code=401)
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise AppError("INVALID_TOKEN", "登录凭证无效或已过期", status_code=401) from exc
    user = await session.get(User, user_id)
    if user is None or not user.enabled:
        raise AppError("USER_DISABLED", "用户不存在或已停用", status_code=401)
    request.state.user_id = user.id
    request.state.username = user.username
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[CurrentUser], Awaitable[User]]:
    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError("FORBIDDEN", "没有执行此操作的权限", status_code=403)
        return user

    return dependency


WarehouseWriter = Annotated[User, Depends(require_roles(Role.SUPER_ADMIN, Role.WAREHOUSE_ADMIN))]
PurchaseWriter = Annotated[User, Depends(require_roles(Role.SUPER_ADMIN, Role.PURCHASE_ADMIN))]
SuperAdmin = Annotated[User, Depends(require_roles(Role.SUPER_ADMIN))]
