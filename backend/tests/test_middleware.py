from __future__ import annotations

from typing import Any

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.core.middleware import RealIPMiddleware


def _scope(headers: list[tuple[bytes, bytes]], client: tuple[str, int] | None = None) -> Scope:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "server": ("testserver", 80),
        "client": client,
        "scheme": "http",
        "method": "GET",
        "root_path": "",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "state": {},
    }


async def _receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _send(message: Message) -> None:
    pass


async def _captured_client(scope: Scope) -> tuple[str, int] | None:
    captured: dict[str, Any] = {}

    async def endpoint(inner_scope: Scope, receive: Receive, send: Send) -> None:
        captured["client"] = inner_scope.get("client")

    await RealIPMiddleware(endpoint)(scope, _receive, _send)
    return captured["client"]


@pytest.mark.asyncio
async def test_real_ip_header_priority() -> None:
    client = await _captured_client(
        _scope(
            [
                (b"eo-connecting-ip", b"203.0.113.10"),
                (b"x-real-ip", b"203.0.113.20"),
                (b"x-forwarded-for", b"203.0.113.30, 10.0.0.1"),
            ],
            ("10.0.0.2", 4321),
        )
    )

    assert client == ("203.0.113.10", 4321)


@pytest.mark.asyncio
async def test_real_ip_uses_first_forwarded_address() -> None:
    client = await _captured_client(
        _scope([(b"x-forwarded-for", b" 2001:db8::1, 10.0.0.1")], ("10.0.0.2", 80))
    )

    assert client == ("2001:db8::1", 80)


@pytest.mark.asyncio
async def test_real_ip_skips_invalid_headers_and_handles_missing_client() -> None:
    client = await _captured_client(
        _scope(
            [(b"eo-connecting-ip", b"invalid"), (b"x-real-ip", b"198.51.100.9")]
        )
    )

    assert client == ("198.51.100.9", 0)


@pytest.mark.asyncio
async def test_real_ip_keeps_original_client_without_valid_proxy_header() -> None:
    client = await _captured_client(
        _scope([(b"x-forwarded-for", b"not-an-ip")], ("10.0.0.2", 1234))
    )

    assert client == ("10.0.0.2", 1234)
