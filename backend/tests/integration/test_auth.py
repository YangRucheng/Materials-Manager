from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_refresh_issues_a_new_token_pair(client: AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "123456"}
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens["refresh_token"]

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["access_token"] != tokens["access_token"]
    assert refreshed.json()["refresh_token"] != tokens["refresh_token"]

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_access_token_cannot_be_used_as_refresh_token(client: AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "123456"}
    )
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login.json()["access_token"]}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_permanent_api_token_authenticates_from_supported_headers(
    client: AsyncClient,
) -> None:
    admin_login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "123456"}
    )
    users = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )
    warehouse_id = next(
        item["id"] for item in users.json()["items"] if item["username"] == "warehouse"
    )
    # 令牌只在重新生成接口一次性返回（库中只存哈希）。
    regenerated = await client.post(
        f"/api/v1/users/{warehouse_id}/api-token/regenerate",
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
        json={"version": next(
            item["version"] for item in users.json()["items"] if item["username"] == "warehouse"
        )},
    )
    assert regenerated.status_code == 200, regenerated.text
    api_token = regenerated.json()["api_token"]
    parsed = UUID(api_token)
    assert parsed.version == 4
    assert str(parsed) == api_token
    assert "api_token" not in admin_login.json()["user"]
    assert all(item["api_token"] is None for item in users.json()["items"])

    for headers in (
        {"X-API-Token": api_token},
        {"Authorization": f"Bearer {api_token}"},
    ):
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["username"] == "warehouse"


@pytest.mark.asyncio
async def test_invalid_api_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={"X-API-Token": "00000000-0000-4000-8000-000000000000"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"
