from __future__ import annotations

from httpx import AsyncClient


async def test_cors_preflight_allows_configured_frontend(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-request-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["vary"] == "Origin"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-max-age"] == "86400"
    assert "POST" in response.headers["access-control-allow-methods"]


async def test_cors_response_exposes_download_and_request_headers(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "content-disposition" in exposed
    assert "x-request-id" in exposed


async def test_cors_reflects_any_origin(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": "https://unknown.example.com"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://unknown.example.com"
    assert response.headers["vary"] == "Origin"
