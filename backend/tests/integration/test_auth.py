from __future__ import annotations

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
