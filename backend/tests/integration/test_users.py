from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models import User
from tests.conftest import auth_headers, create_stock


async def _clear_api_token_enc(user_id: int) -> None:
    """模拟升级前的旧数据：只保留哈希、清空 Fernet 密文。"""
    async with SessionLocal() as session:
        item = await session.get(User, user_id)
        assert item is not None
        item.api_token_enc = ""
        await session.commit()


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
async def test_api_token_is_unique_and_can_be_regenerated(client: AsyncClient) -> None:
    admin = await auth_headers(client, "admin")
    created = await client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "api-user",
            "password": "123456",
            "display_name": "接口用户",
            "role": "READ_ONLY",
            "enabled": True,
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()
    old_token = user["api_token"]
    assert UUID(old_token).version == 4

    authenticated = await client.get(
        "/api/v1/auth/me", headers={"X-API-Token": old_token}
    )
    assert authenticated.status_code == 200

    regenerated = await client.post(
        f"/api/v1/users/{user['id']}/api-token/regenerate",
        headers=admin,
        json={"version": user["version"]},
    )
    assert regenerated.status_code == 200, regenerated.text
    new_token = regenerated.json()["api_token"]
    assert UUID(new_token).version == 4
    assert new_token != old_token

    rejected = await client.get("/api/v1/auth/me", headers={"X-API-Token": old_token})
    assert rejected.status_code == 401
    accepted = await client.get("/api/v1/auth/me", headers={"X-API-Token": new_token})
    assert accepted.status_code == 200


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


@pytest.mark.asyncio
async def test_api_token_is_echoed_on_every_read(client: AsyncClient) -> None:
    """回显约定：新建返回的令牌，之后每次列表/编辑读取都应回显同一明文，无需重新生成。"""
    admin = await auth_headers(client, "admin")
    created = await client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "echo-user",
            "password": "123456",
            "display_name": "回显用户",
            "role": "READ_ONLY",
            "enabled": True,
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()
    token = user["api_token"]
    assert token is not None and UUID(token).version == 4

    listed = await client.get("/api/v1/users?page_size=200", headers=admin)
    assert listed.status_code == 200
    row = next(i for i in listed.json()["items"] if i["id"] == user["id"])
    assert row["api_token"] == token

    patched = await client.patch(
        f"/api/v1/users/{user['id']}",
        headers=admin,
        json={"display_name": "回显用户改名", "version": user["version"]},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["api_token"] == token

    # 二次读取仍稳定回显（可反复复制，绝不要求重新生成）。
    listed_again = await client.get("/api/v1/users?page_size=200", headers=admin)
    row_again = next(i for i in listed_again.json()["items"] if i["id"] == user["id"])
    assert row_again["api_token"] == token


@pytest.mark.asyncio
async def test_legacy_hash_only_token_backfilled_and_echoed_after_use(client: AsyncClient) -> None:
    """懒迁移：只有哈希的旧数据初次读取回显 None，令牌成功调用一次后自动回写密文并持续回显。"""
    admin = await auth_headers(client, "admin")
    created = await client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "legacy-user",
            "password": "123456",
            "display_name": "旧数据用户",
            "role": "READ_ONLY",
            "enabled": True,
        },
    )
    user = created.json()
    token = user["api_token"]
    assert token is not None

    # 抹掉密文，模拟升级到「可回显」版本之前、库里只有哈希的历史用户。
    await _clear_api_token_enc(user["id"])

    listed = await client.get("/api/v1/users?page_size=200", headers=admin)
    row = next(i for i in listed.json()["items"] if i["id"] == user["id"])
    assert row["api_token"] is None  # 旧数据尚未加密，读取降级为 None，不报错

    # 令牌成功用于一次接口调用（认证走哈希查找）。
    authed = await client.get("/api/v1/auth/me", headers={"X-API-Token": token})
    assert authed.status_code == 200, authed.text
    assert authed.json()["username"] == "legacy-user"

    # 认证路径已把明文加密回写，此后无需重新生成即可回显。
    async with SessionLocal() as session:
        item = await session.get(User, user["id"])
        assert item is not None and item.api_token_enc != ""
    after = await client.get("/api/v1/users?page_size=200", headers=admin)
    row_after = next(i for i in after.json()["items"] if i["id"] == user["id"])
    assert row_after["api_token"] == token
