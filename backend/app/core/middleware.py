from __future__ import annotations

import logging
import time
import uuid
from ipaddress import ip_address
from urllib.parse import urlsplit

from fastapi import Request, Response
from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("spare_parts.api")


def _real_ip(scope: Scope) -> str | None:
    headers = Headers(scope=scope)
    candidates = (
        headers.get("EO-Connecting-IP"),
        headers.get("X-Real-IP"),
        (headers.get("X-Forwarded-For") or "").split(",", 1)[0],
    )
    for value in candidates:
        if not value or not (candidate := value.strip()):
            continue
        try:
            return str(ip_address(candidate))
        except ValueError:
            continue
    return None


def _origin_from_url(value: str | None) -> str | None:
    if not value or not (url := value.strip()):
        return None
    if url == "null":
        return url
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _cors_origin(headers: Headers, allowed_origins: list[str]) -> str | None:
    """返回允许回显的 Origin。

    Referer 优先（兼容不发 Origin 的内嵌 WebView/微信），缺失时回退 Origin。
    仅当来源在白名单内才回显；不在白名单返回 None（浏览器会拦截跨域响应）。
    """
    origin = _origin_from_url(headers.get("Referer"))
    if origin is None:
        origin = _origin_from_url(headers.get("Origin"))
    if origin is None:
        return None
    if not allowed_origins or _is_allowed_origin(origin, allowed_origins):
        return origin
    return None


def _is_allowed_origin(origin: str, allowed_origins: list[str]) -> bool:
    """精确匹配或 host 后缀匹配（.example.com 匹配 app.example.com 等子域）。"""
    parsed = urlsplit(origin)
    host = parsed.netloc.lower()
    if origin in allowed_origins:
        return True
    return any(
        allowed.lower() in ("*", host)
        or (allowed.lower().startswith(".") and host.endswith(allowed.lower()))
        for allowed in allowed_origins
    )


class RefererCORSMiddleware:
    """Allow cross-origin requests using Referer first, then Origin as fallback."""

    _allow_methods = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
    _expose_headers = "Content-Disposition, X-Request-ID"

    def __init__(
        self,
        app: ASGIApp,
        *,
        allow_credentials: bool = True,
        max_age: int = 86400,
        allowed_origins: list[str] | None = None,
    ) -> None:
        self.app = app
        self.allow_credentials = allow_credentials
        self.max_age = max_age
        # 优先使用显式传入的白名单；否则在请求时读 settings.cors_origins
        # （settings 为进程级单例，启动时从环境变量加载，生产环境安全且便于测试）。
        self.allowed_origins = allowed_origins

    def _apply_headers(self, headers: MutableHeaders, origin: str) -> None:
        headers["Access-Control-Allow-Origin"] = origin
        if self.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Expose-Headers"] = self._expose_headers
        headers.add_vary_header("Origin")
        headers.add_vary_header("Referer")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = Headers(scope=scope)
        allowed = self.allowed_origins
        if allowed is None:
            from app.core.config import settings

            allowed = settings.cors_origins
        origin = _cors_origin(request_headers, allowed)
        if origin is None:
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS" and request_headers.get("Access-Control-Request-Method"):
            response_headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": self._allow_methods,
                "Access-Control-Max-Age": str(self.max_age),
                "Access-Control-Expose-Headers": self._expose_headers,
                "Vary": "Origin, Referer",
            }
            if self.allow_credentials:
                response_headers["Access-Control-Allow-Credentials"] = "true"
            if requested_headers := request_headers.get("Access-Control-Request-Headers"):
                response_headers["Access-Control-Allow-Headers"] = requested_headers
            if request_headers.get("Access-Control-Request-Private-Network") == "true":
                response_headers["Access-Control-Allow-Private-Network"] = "true"
            response = PlainTextResponse("OK", status_code=200, headers=response_headers)
            await response(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                self._apply_headers(MutableHeaders(scope=message), origin)
            await send(message)

        await self.app(scope, receive, send_with_cors)


class RealIPMiddleware:
    """Expose the client IP supplied by the trusted edge proxy to downstream requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and (real_ip := _real_ip(scope)):
            scope = dict(scope)
            client = scope.get("client")
            scope["client"] = (real_ip, client[1] if client else 0)
        await self.app(scope, receive, send)


async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """为每个请求注入 request_id 并记录访问日志。"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:128]
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    client_ip = request.client.host if request.client else "unknown"
    logger.info(
        "HTTP %s %s -> %s | %.2f ms | client_ip=%s | user=%s | request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
        client_ip,
        getattr(request.state, "username", "anonymous"),
        request_id,
    )
    return response
