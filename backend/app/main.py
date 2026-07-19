from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint

from app.api.v1 import router as api_router
from app.core.config import settings
from app.core.database import engine
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.schema import schema_differences

logger = logging.getLogger("spare_parts.api")


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(settings.log_dir, settings.log_backup_count)
    logger.info(
        "service started environment=%s log_dir=%s",
        settings.environment,
        settings.log_dir,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:128]
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "HTTP %s %s -> %s | %.2f ms | user=%s | request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
        getattr(request.state, "username", "anonymous"),
        request_id,
    )
    return response


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="请求参数校验失败",
        details={"errors": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(IntegrityError)
async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("database integrity error request_id=%s", request.state.request_id)
    return error_response(
        request,
        status_code=409,
        code="DATA_CONFLICT",
        message="数据约束冲突",
    )


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error(
        "database unavailable request_id=%s error_type=%s",
        request.state.request_id,
        type(exc).__name__,
    )
    return error_response(
        request,
        status_code=503,
        code="DATABASE_UNAVAILABLE",
        message="数据库暂时不可用，请稍后重试",
    )


@app.exception_handler(Exception)
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


@app.get("/health", include_in_schema=False)
async def health(request: Request) -> JSONResponse:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            differences = await connection.run_sync(schema_differences)
    except Exception as exc:
        logger.warning("database health check failed error_type=%s", type(exc).__name__)
        return error_response(
            request,
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="数据库连接不可用",
        )
    if differences:
        logger.error("database schema mismatch differences=%s", differences)
        return error_response(
            request,
            status_code=503,
            code="DATABASE_SCHEMA_MISMATCH",
            message="数据库表结构与当前版本不一致，请重建数据库并导入最新版 init.sql",
            details=differences,
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})


app.include_router(api_router, prefix="/api/v1")
