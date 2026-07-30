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
from app.models import MiniProgramUser, User

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
        if payload.get("token_type") not in (None, "management", "management_access"):
            raise ValueError("wrong token type")
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


async def get_current_mini_program_user(
    request: Request,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> MiniProgramUser:
    if credentials is None:
        raise AppError("UNAUTHORIZED", "请先登录", status_code=401)
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("token_type") != "mini_program":
            raise ValueError("wrong token type")
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise AppError("INVALID_TOKEN", "登录凭证无效或已过期", status_code=401) from exc
    user = await session.get(MiniProgramUser, user_id)
    if user is None:
        raise AppError("INVALID_TOKEN", "登录凭证无效或已过期", status_code=401)
    if not user.enabled:
        raise AppError("ACCOUNT_DISABLED", "您的账号待审核，请联系管理员", status_code=403)
    request.state.mini_program_user_id = user.id
    request.state.username = f"mini:{user.id}"
    return user


CurrentMiniProgramUser = Annotated[MiniProgramUser, Depends(get_current_mini_program_user)]


async def get_mini_program_registration_openid(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> tuple[str, str]:
    if credentials is None:
        raise AppError("UNAUTHORIZED", "请先完成微信登录", status_code=401)
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("token_type") != "mini_program_registration":
            raise ValueError("wrong token type")
        openid = str(payload["sub"])
        app_id = str(payload["app_id"])
        if not app_id or not openid:
            raise ValueError("missing mini program identity")
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise AppError("INVALID_TOKEN", "注册凭证无效或已过期", status_code=401) from exc
    return app_id, openid


MiniProgramRegistrationOpenId = Annotated[
    tuple[str, str], Depends(get_mini_program_registration_openid)
]


def require_roles(*roles: Role) -> Callable[[CurrentUser], Awaitable[User]]:
    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError("FORBIDDEN", "没有执行此操作的权限", status_code=403)
        return user

    return dependency


WarehouseWriter = Annotated[User, Depends(require_roles(Role.SUPER_ADMIN, Role.WAREHOUSE_ADMIN))]
PurchaseWriter = Annotated[User, Depends(require_roles(Role.SUPER_ADMIN, Role.PURCHASE_ADMIN))]
SuperAdmin = Annotated[User, Depends(require_roles(Role.SUPER_ADMIN))]
