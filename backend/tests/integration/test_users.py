from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_stock


@pytest.mark.asyncio
async def test_username_can_change_without_changing_hidden_user_id(client: AsyncClient) -> None:
    admin = await auth_headers(client, "admin")
    created = await client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "temporary",
            "password": "123456",
            "display_name": "临时用户",
            "role": "READ_ONLY",
            "enabled": True,
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()

    updated = await client.patch(
        f"/api/v1/users/{user['id']}",
        headers=admin,
        json={"username": "renamed", "version": user["version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == user["id"]
    assert updated.json()["username"] == "renamed"

    old_login = await client.post(
        "/api/v1/auth/login", json={"username": "temporary", "password": "123456"}
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login", json={"username": "renamed", "password": "123456"}
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_user_without_references_can_be_deleted(client: AsyncClient) -> None:
    admin = await auth_headers(client, "admin")
    created = await client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "unused",
            "password": "123456",
            "display_name": "未使用用户",
            "role": "READ_ONLY",
            "enabled": True,
        },
    )
    user_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/users/{user_id}", headers=admin)
    assert deleted.status_code == 204, deleted.text
    users = await client.get("/api/v1/users?page_size=200", headers=admin)
    assert user_id not in {item["id"] for item in users.json()["items"]}


@pytest.mark.asyncio
async def test_operation_does_not_reference_authenticated_user(
    client: AsyncClient,
) -> None:
    admin = await auth_headers(client, "admin")
    warehouse = await auth_headers(client, "warehouse")
    material_id = await create_stock(client, warehouse, "操作人关联测试")
    response = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json={
            "client_request_id": "hidden-operator-id",
            "occurred_at": "2026-07-18T10:00:00+08:00",
            "source_type": "MANUAL",
            "business_reason": "验证操作人内部关联",
            "lines": [{"stock_material_id": material_id, "quantity": "1"}],
        },
    )
    assert response.status_code == 201, response.text
    assert "operator_id" not in response.json()
    assert "operator_name" not in response.json()

    deleted = await client.delete("/api/v1/users/2", headers=admin)
    assert deleted.status_code == 204, deleted.text
