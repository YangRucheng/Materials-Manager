from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import router as api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exception_handlers import error_response, register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RealIPMiddleware, RefererCORSMiddleware, request_context
from app.mcp_server import bind_application, mcp, mcp_http_app
from app.services import (
    ai_search_service,
    purchase_plan_cleanup_service,
    webhook_service,
)

logger = logging.getLogger("spare_parts.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(settings.log_dir, settings.log_backup_count)
    logger.info(
        "service started environment=%s log_dir=%s",
        settings.environment,
        settings.log_dir,
    )
    webhook_stop_event = asyncio.Event()
    webhook_worker = asyncio.create_task(
        webhook_service.run_delivery_worker(webhook_stop_event),
        name="webhook-delivery-worker",
    )
    cleanup_stop_event = asyncio.Event()
    cleanup_worker: asyncio.Task[None] | None = None
    if settings.purchase_plan_cleanup_enabled:
        cleanup_worker = asyncio.create_task(
            purchase_plan_cleanup_service.run_cleanup_worker(cleanup_stop_event),
            name="purchase-plan-cleanup-worker",
        )
    try:
        async with mcp.session_manager.run():
            yield
    finally:
        webhook_stop_event.set()
        await webhook_worker
        await webhook_service.close_client()
        cleanup_stop_event.set()
        if cleanup_worker is not None:
            await cleanup_worker
        await ai_search_service.close_client()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/docs",
)
app.add_middleware(
    RefererCORSMiddleware,
    allow_credentials=settings.cors_allow_credentials,
    max_age=settings.cors_max_age,
)
# 注意注册顺序：后注册的中间件更外层（先处理请求）。
# request_context 需在 RealIP 内层，才能读到 RealIP 改写后的真实客户端 IP。
app.middleware("http")(request_context)
app.add_middleware(RealIPMiddleware)
register_exception_handlers(app)


@app.get("/health", include_in_schema=False)
async def health(request: Request) -> JSONResponse:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("database health check failed error_type=%s", type(exc).__name__)
        return error_response(
            request,
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="数据库连接不可用",
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})


app.include_router(api_router, prefix="/api/v1")
bind_application(app)
app.mount("/api/v1/mcp", mcp_http_app, name="mcp")
