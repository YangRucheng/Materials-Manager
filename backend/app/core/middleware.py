from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


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


def _cors_origin(headers: Headers) -> str | None:
    return _origin_from_url(headers.get("Referer")) or _origin_from_url(headers.get("Origin"))


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
    ) -> None:
        self.app = app
        self.allow_credentials = allow_credentials
        self.max_age = max_age

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
        origin = _cors_origin(request_headers)
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
