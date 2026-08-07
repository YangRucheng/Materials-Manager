"""全局异常处理：统一错误响应构造 + 各类异常 → 结构化业务错误体。

从 main.py 拆出，对外 API 契约不变（路由、状态码、错误体结构完全一致）。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import (
    DisconnectionError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.exc import (
    TimeoutError as SQLAlchemyTimeoutError,
)
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError

logger = logging.getLogger("spare_parts.api")

MYSQL_QUERY_ERROR_CODES = {
    1052,  # Column is ambiguous.
    1054,  # Unknown column.
    1064,  # SQL syntax error.
    1066,  # Duplicate table alias.
    1109,  # Unknown table.
    1146,  # Table does not exist.
}


def is_database_query_error(exc: SQLAlchemyError) -> bool:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    return bool(args and isinstance(args[0], int) and args[0] in MYSQL_QUERY_ERROR_CODES)


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | list[Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # 约定：禁止对外产生 404 状态码（见 docs/api-error-conventions.md）。
    # 未匹配的 API 路径（框架级 404）重映射为 400 + code=ROUTE_NOT_FOUND，返回结构化业务错误体。
    # 其余 Starlette HTTP 异常（如 405/422）保持原状态码透传。
    if exc.status_code == 404:
        return error_response(
            request,
            status_code=400,
            code="ROUTE_NOT_FOUND",
            message="接口路径不存在",
        )
    return error_response(
        request,
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=str(exc.detail) if exc.detail else "请求错误",
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="请求参数校验失败",
        details={"errors": jsonable_encoder(exc.errors())},
    )


async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning(
        "database integrity error request_id=%s",
        request.state.request_id,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return error_response(
        request,
        status_code=409,
        code="DATA_CONFLICT",
        message="数据约束冲突",
    )


async def handle_database_programming_error(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.error(
        "database query error request_id=%s error_type=%s",
        request.state.request_id,
        type(exc).__name__,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return error_response(
        request,
        status_code=500,
        code="DATABASE_QUERY_ERROR",
        message="数据库查询执行失败，请联系管理员",
    )


async def handle_database_unavailable(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    if is_database_query_error(exc):
        return await handle_database_programming_error(request, exc)
    logger.error(
        "database unavailable request_id=%s error_type=%s",
        request.state.request_id,
        type(exc).__name__,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return error_response(
        request,
        status_code=503,
        code="DATABASE_UNAVAILABLE",
        message="数据库暂时不可用，请稍后重试",
    )


async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error(
        "database error request_id=%s error_type=%s",
        request.state.request_id,
        type(exc).__name__,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return error_response(
        request,
        status_code=500,
        code="DATABASE_ERROR",
        message="数据库操作失败，请联系管理员",
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unexpected server error request_id=%s error_type=%s",
        request.state.request_id,
        type(exc).__name__,
    )
    return error_response(
        request,
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="服务内部异常，请联系管理员",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全部全局异常处理器。

    Starlette 运行时会按注册的异常类型调用对应 handler；
    mypy 的协变检查对「收窄异常类型的 handler」过于严格，故加 type: ignore[arg-type]。
    """
    app.add_exception_handler(AppError, handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(IntegrityError, handle_integrity_error)  # type: ignore[arg-type]
    app.add_exception_handler(ProgrammingError, handle_database_programming_error)  # type: ignore[arg-type]
    app.add_exception_handler(OperationalError, handle_database_unavailable)  # type: ignore[arg-type]
    app.add_exception_handler(InterfaceError, handle_database_unavailable)  # type: ignore[arg-type]
    app.add_exception_handler(DisconnectionError, handle_database_unavailable)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyTimeoutError, handle_database_unavailable)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, handle_database_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_unexpected_error)
