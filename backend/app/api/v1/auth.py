import jwt
from fastapi import APIRouter
from sqlalchemy import select

from app.core.errors import AppError
from app.core.permissions import CurrentUser, DbSession
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    verify_password,
)
from app.models import User
from app.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    TokenPairResponse,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, session: DbSession) -> LoginResponse:
    user = await session.scalar(select(User).where(User.username == data.username))
    if user is None or not user.enabled or not verify_password(data.password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "用户名或密码错误", status_code=401)
    return LoginResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id, user.version),
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(data: RefreshTokenRequest, session: DbSession) -> TokenPairResponse:
    try:
        payload = decode_access_token(data.refresh_token)
        if payload.get("token_type") != "management_refresh":
            raise ValueError("wrong token type")
        user_id = int(payload["sub"])
        token_version = int(payload["version"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise AppError("INVALID_REFRESH_TOKEN", "续期凭证无效或已过期", status_code=401) from exc

    user = await session.get(User, user_id)
    if user is None or not user.enabled or user.version != token_version:
        raise AppError("INVALID_REFRESH_TOKEN", "续期凭证无效或已过期", status_code=401)
    return TokenPairResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id, user.version),
    )


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
