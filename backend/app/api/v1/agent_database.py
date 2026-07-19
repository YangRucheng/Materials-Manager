from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import select

from app.core.errors import AppError
from app.core.permissions import DbSession
from app.core.security import verify_password
from app.domain.enums import Role
from app.models import User
from app.schemas import (
    AgentDatabaseExecuteRead,
    AgentDatabaseExecuteRequest,
    AgentDatabaseSchemaRead,
)
from app.services import agent_database_service

router = APIRouter(prefix="/agent/database", tags=["Agent 数据库"])


async def authenticate_agent_database(
    request: Request,
    session: DbSession,
    username: Annotated[str | None, Header(alias="X-Agent-Username")] = None,
    password: Annotated[str | None, Header(alias="X-Agent-Password")] = None,
) -> User:
    user: User | None = None
    if username and len(username) <= 64:
        user = await session.scalar(select(User).where(User.username == username))
    if (
        user is None
        or not password
        or len(password) > 128
        or not user.enabled
        or user.role != Role.SUPER_ADMIN
        or not verify_password(password, user.password_hash)
    ):
        raise AppError(
            "INVALID_AGENT_DATABASE_CREDENTIALS",
            "Agent 数据库接口需要有效的超级管理员账号和密码",
            status_code=401,
        )
    request.state.user_id = user.id
    request.state.username = user.username
    return user


AgentDatabaseAdmin = Annotated[User, Depends(authenticate_agent_database)]


@router.get("/schema", response_model=AgentDatabaseSchemaRead)
async def database_schema(
    response: Response,
    session: DbSession,
    user: AgentDatabaseAdmin,
) -> AgentDatabaseSchemaRead:
    response.headers["Cache-Control"] = "no-store"
    return AgentDatabaseSchemaRead(**await agent_database_service.read_schema(session))


@router.post("/execute", response_model=AgentDatabaseExecuteRead)
async def execute_database_sql(
    data: AgentDatabaseExecuteRequest,
    response: Response,
    session: DbSession,
    user: AgentDatabaseAdmin,
) -> AgentDatabaseExecuteRead:
    response.headers["Cache-Control"] = "no-store"
    return await agent_database_service.execute_sql(session, data, user.username)
