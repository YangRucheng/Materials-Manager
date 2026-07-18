from fastapi import APIRouter
from sqlalchemy import select

from app.core.errors import AppError
from app.core.permissions import CurrentUser, DbSession
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserRead

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, session: DbSession) -> LoginResponse:
    user = await session.scalar(select(User).where(User.username == data.username))
    if user is None or not user.enabled or not verify_password(data.password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "用户名或密码错误", status_code=401)
    return LoginResponse(
        access_token=create_access_token(user.id), user=UserRead.model_validate(user)
    )


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
