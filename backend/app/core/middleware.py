from __future__ import annotations

from ipaddress import ip_address

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send


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
