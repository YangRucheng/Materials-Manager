from __future__ import annotations

from httpx import AsyncClient


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
    response = await client.post(
        "/auth/login",
        headers={
            "Referer": "https://frontend.example.com/login",
            "Origin": "https://frontend.example.com",
        },
        json={},
    )

    assert response.status_code == 404
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
