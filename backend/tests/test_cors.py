from __future__ import annotations

from httpx import AsyncClient

from app.core.config import settings


def _vary_values(response) -> set[str]:
    return {item.strip().lower() for item in response.headers["vary"].split(",")}


async def test_cors_preflight_prefers_referer(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Referer": "https://frontend.example.com/login?from=home",
            "Origin": "https://origin-fallback.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-request-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frontend.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-max-age"] == "86400"
    assert response.headers["access-control-allow-headers"] == (
        "authorization,content-type,x-request-id"
    )
    assert {"origin", "referer"} <= _vary_values(response)


async def test_cors_preflight_falls_back_to_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://frontend.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frontend.example.com"


async def test_cors_headers_are_added_to_not_found_response(client: AsyncClient) -> None:
    # 框架级路由 404 会被全局处理重映射为 400 + ROUTE_NOT_FOUND（禁止 404，见
    # docs/api-error-conventions.md），CORS 头仍应补齐在结构化错误响应上。
    response = await client.post(
        "/auth/login",
        headers={
            "Referer": "https://frontend.example.com/login",
            "Origin": "https://frontend.example.com",
        },
        json={},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ROUTE_NOT_FOUND"
    assert response.headers["access-control-allow-origin"] == "https://frontend.example.com"
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "content-disposition" in exposed
    assert "x-request-id" in exposed


async def test_cors_ignores_malformed_referer_and_uses_origin(client: AsyncClient) -> None:
    response = await client.get(
        "/health",
        headers={"Referer": "not-a-url", "Origin": "https://frontend.example.com"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frontend.example.com"


async def test_response_without_referer_or_origin_has_no_cors_headers(
    client: AsyncClient,
) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_cors_whitelist_rejects_unknown_origin(client: AsyncClient) -> None:
    """配置白名单后，未知来源不反射 CORS 头（浏览器拦截跨域）。"""
    original = settings.cors_origins
    settings.cors_origins = ["https://frontend.example.com", ".example.com"]
    try:
        response = await client.get(
            "/health",
            headers={"Origin": "https://evil-attacker.com", "Referer": "https://evil-attacker.com/x"},
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

        # 白名单内来源正常放行
        allowed = await client.get(
            "/health",
            headers={"Origin": "https://app.example.com", "Referer": "https://app.example.com/x"},
        )
        assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"

        # 子域后缀匹配（.example.com 匹配 app.example.com）
        sub = await client.get(
            "/health",
            headers={"Referer": "https://sub.example.com/page"},
        )
        assert sub.headers["access-control-allow-origin"] == "https://sub.example.com"
    finally:
        settings.cors_origins = original
