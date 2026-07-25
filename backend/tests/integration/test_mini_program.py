from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services import mini_program_service
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_wechat_profile_registration_scan_and_outbound_flow(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_exchange_wechat_code(code: str) -> str:
        assert code == "temporary-login-code"
        return "openid-for-scan-user"

    monkeypatch.setattr(
        mini_program_service,
        "exchange_wechat_code",
        fake_exchange_wechat_code,
    )
    admin = await auth_headers(client, "admin")
    warehouse = await auth_headers(client, "warehouse")

    login = await client.post(
        "/api/v1/mini-program/auth/wx-login",
        json={"code": "temporary-login-code"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["requires_profile"] is True
    assert login.json()["access_token"] is None
    assert login.json()["user"] is None
    registration_token = login.json()["registration_token"]
    assert registration_token

    users_before_profile = await client.get(
        "/api/v1/mini-program-users", headers=admin
    )
    assert users_before_profile.status_code == 200
    assert users_before_profile.json()["total"] == 0

    manual_create = await client.post(
        "/api/v1/mini-program-users",
        headers=admin,
        json={"display_name": "不应创建"},
    )
    assert manual_create.status_code == 405

    profile = await client.post(
        "/api/v1/mini-program/profile",
        headers={"Authorization": f"Bearer {registration_token}"},
        json={"display_name": "扫码出库员"},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["requires_profile"] is False
    assert profile.json()["registration_token"] is None
    created_user = profile.json()["user"]
    assert created_user["wechat_openid"] == "openid-for-scan-user"
    assert created_user["display_name"] == "扫码出库员"
    mini_headers = {"Authorization": f"Bearer {profile.json()['access_token']}"}

    replayed_profile = await client.post(
        "/api/v1/mini-program/profile",
        headers={"Authorization": f"Bearer {registration_token}"},
        json={"display_name": "试图修改姓名"},
    )
    assert replayed_profile.status_code == 200, replayed_profile.text
    assert replayed_profile.json()["user"]["id"] == created_user["id"]
    assert replayed_profile.json()["user"]["display_name"] == "扫码出库员"

    material = await client.post(
        "/api/v1/stock-materials",
        headers=warehouse,
        json={
            "name": "扫码测试物资",
            "model_spec": "SCAN-001",
            "unit_id": 1,
            "image_ids": [],
        },
    )
    assert material.status_code == 201, material.text
    material_data = material.json()

    inbound = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json={
            "client_request_id": "mini-program-seed-inbound",
            "occurred_at": "2026-07-25T10:00:00+08:00",
            "source_type": "MANUAL",
            "business_reason": "扫码出库测试入库",
            "lines": [{"stock_material_id": material_data["id"], "quantity": "5"}],
        },
    )
    assert inbound.status_code == 201, inbound.text

    admin_token_rejected = await client.get(
        f"/api/v1/mini-program/materials/{material_data['uuid']}", headers=admin
    )
    assert admin_token_rejected.status_code == 401
    mini_token_rejected = await client.get("/api/v1/users", headers=mini_headers)
    assert mini_token_rejected.status_code == 401

    scanned = await client.get(
        f"/api/v1/mini-program/materials/{material_data['uuid']}", headers=mini_headers
    )
    assert scanned.status_code == 200, scanned.text
    assert scanned.json() == {
        "uuid": material_data["uuid"],
        "name": "扫码测试物资",
        "model_spec": "SCAN-001",
        "unit_name": "个",
        "current_qty": "5",
    }

    payload = {
        "client_request_id": "mini-program-outbound-001",
        "material_uuid": material_data["uuid"],
        "occurred_at": "2026-07-25T11:00:00+08:00",
        "quantity": "2",
        "business_reason": "现场检修领用",
        "receiver_unit": "电气检修班",
        "subitem_no": "01-01",
    }
    outbound = await client.post(
        "/api/v1/mini-program/outbound", headers=mini_headers, json=payload
    )
    repeated = await client.post(
        "/api/v1/mini-program/outbound", headers=mini_headers, json=payload
    )
    assert outbound.status_code == repeated.status_code == 201
    assert outbound.json()["operation_id"] == repeated.json()["operation_id"]
    assert outbound.json()["after_qty"] == "3"
    assert outbound.json()["executed_by"] == "扫码出库员"
    assert outbound.json()["receiver_name"] == "扫码出库员"

    operation = await client.get(
        f"/api/v1/inventory/operations/{outbound.json()['operation_id']}", headers=warehouse
    )
    assert operation.status_code == 200, operation.text
    assert operation.json()["mini_program_user_id"] == created_user["id"]
    assert operation.json()["mini_program_user_name"] == "扫码出库员"

    rename = await client.patch(
        f"/api/v1/mini-program-users/{created_user['id']}",
        headers=admin,
        json={"display_name": "管理员修改", "version": created_user["version"]},
    )
    assert rename.status_code == 200, rename.text
    assert rename.json()["display_name"] == "管理员修改"

    repeated_login = await client.post(
        "/api/v1/mini-program/auth/wx-login",
        json={"code": "temporary-login-code"},
    )
    assert repeated_login.status_code == 200, repeated_login.text
    assert repeated_login.json()["requires_profile"] is False
    assert repeated_login.json()["registration_token"] is None
    assert repeated_login.json()["user"]["id"] == created_user["id"]
    assert repeated_login.json()["user"]["display_name"] == "管理员修改"


@pytest.mark.asyncio
async def test_mini_program_users_require_super_admin(client: AsyncClient) -> None:
    warehouse = await auth_headers(client, "warehouse")
    response = await client.get("/api/v1/mini-program-users", headers=warehouse)
    assert response.status_code == 403
