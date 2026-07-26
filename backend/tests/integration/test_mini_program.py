from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from PIL import Image

from app.domain.enums import MiniProgramCodeEnv
from app.services import ai_search_service, mini_program_service
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
        json={
            "display_name": "扫码出库员",
            "department_name": "华星检修维护部电气车间",
        },
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["requires_profile"] is False
    assert profile.json()["registration_token"] is None
    created_user = profile.json()["user"]
    assert created_user["wechat_openid"] == "openid-for-scan-user"
    assert created_user["display_name"] == "扫码出库员"
    assert created_user["department_name"] == "华星检修维护部电气车间"
    mini_headers = {"Authorization": f"Bearer {profile.json()['access_token']}"}

    replayed_profile = await client.post(
        "/api/v1/mini-program/profile",
        headers={"Authorization": f"Bearer {registration_token}"},
        json={
            "display_name": "试图修改姓名",
            "department_name": "试图修改单位",
        },
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

    async def fake_generate_unlimited_material_code(material_uuid, env):
        assert str(material_uuid) == material_data["uuid"]
        assert env == MiniProgramCodeEnv.TRIAL
        return b"mini-program-code"

    monkeypatch.setattr(
        mini_program_service,
        "generate_unlimited_material_code",
        fake_generate_unlimited_material_code,
    )
    async def fake_mini_program_code_env(_session):
        return MiniProgramCodeEnv.TRIAL

    monkeypatch.setattr(
        ai_search_service,
        "get_mini_program_code_env",
        fake_mini_program_code_env,
    )
    mini_program_code_entry_url = (
        f"/api/v1/stock-materials/{material_data['id']}/mini-program-code"
    )
    mini_program_code_url = (
        f"/api/v1/stock-materials/mini-program-codes/{material_data['uuid']}"
    )
    redirect = await client.get(mini_program_code_entry_url, headers=warehouse)
    missing_env = await client.get(mini_program_code_url, headers=warehouse)
    invalid_env = await client.get(
        mini_program_code_url, headers=warehouse, params={"env": "develop"}
    )
    assert redirect.status_code == 307
    assert redirect.headers["cache-control"] == "no-store"
    assert redirect.headers["location"].endswith(
        f"/api/v1/stock-materials/mini-program-codes/{material_data['uuid']}?env=trial"
    )
    assert missing_env.status_code == 422
    assert invalid_env.status_code == 422

    material_code = await client.get(
        redirect.headers["location"],
        headers=warehouse,
    )
    assert material_code.status_code == 200, material_code.text
    assert material_code.headers["content-type"] == "image/png"
    assert material_code.headers["cache-control"] == (
        "public, max-age=31536000, s-maxage=31536000, immutable"
    )
    assert material_code.content == b"mini-program-code"

    inbound = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json={
            "client_request_id": "mini-program-seed-inbound",
            "occurred_at": "2026-07-25T10:00:00+08:00",
            "source_type": "MANUAL",
            "business_reason": "扫码出库测试入库",
            "lines": [{"stock_material_id": material_data["id"], "quantity": "10"}],
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
        "current_qty": "10",
        "stock_status": "normal",
        "minimum_qty": None,
        "remark": None,
        "images": [],
    }

    forged_mini_program_source = await client.post(
        "/api/v1/inventory/outbounds",
        headers=warehouse,
        json={
            "client_request_id": "forged-mini-program-source",
            "occurred_at": "2026-07-25T10:30:00+08:00",
            "source_type": "MINI_PROGRAM",
            "business_reason": "不应允许伪造来源",
            "receiver_name": "管理端用户",
            "lines": [{"stock_material_id": material_data["id"], "quantity": "1"}],
        },
    )
    assert forged_mini_program_source.status_code == 400
    assert forged_mini_program_source.json()["code"] == "INVALID_SOURCE_TYPE"

    payload = {
        "client_request_id": "mini-program-outbound-001",
        "material_uuid": material_data["uuid"],
        "occurred_at": "2026-07-25T11:00:00+08:00",
        "quantity": "2",
        "business_reason": "现场检修领用",
        "receiver_unit": "",
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
    assert outbound.json()["after_qty"] == "8"
    assert outbound.json()["executed_by"] == "扫码出库员"
    assert outbound.json()["receiver_name"] == "扫码出库员"
    assert outbound.json()["receiver_unit"] is None

    operation = await client.get(
        f"/api/v1/inventory/operations/{outbound.json()['operation_id']}", headers=warehouse
    )
    assert operation.status_code == 200, operation.text
    assert operation.json()["source_type"] == "MINI_PROGRAM"
    assert operation.json()["mini_program_user_id"] == created_user["id"]
    assert operation.json()["mini_program_user_name"] == "扫码出库员"
    assert operation.json()["receiver_unit"] is None

    mini_program_operations = await client.get(
        "/api/v1/inventory/operations",
        headers=warehouse,
        params={"source_type": "MINI_PROGRAM"},
    )
    manual_operations = await client.get(
        "/api/v1/inventory/operations",
        headers=warehouse,
        params={"source_type": "MANUAL"},
    )
    assert mini_program_operations.status_code == manual_operations.status_code == 200
    assert outbound.json()["operation_id"] in {
        item["id"] for item in mini_program_operations.json()["items"]
    }
    assert outbound.json()["operation_id"] not in {
        item["id"] for item in manual_operations.json()["items"]
    }

    for index, reason in enumerate(["全员用途一", "全员用途二", "全员用途三", "全员用途四"]):
        system_outbound = await client.post(
            "/api/v1/inventory/outbounds",
            headers=warehouse,
            json={
                "client_request_id": f"system-reason-{index}",
                "occurred_at": f"2026-07-25T{12 + index}:00:00+08:00",
                "source_type": "MANUAL",
                "business_reason": reason,
                "receiver_name": "系统用户",
                "lines": [{"stock_material_id": material_data["id"], "quantity": "1"}],
            },
        )
        assert system_outbound.status_code == 201, system_outbound.text

    reason_options = await client.get(
        "/api/v1/mini-program/outbound-reasons", headers=mini_headers
    )
    assert reason_options.status_code == 200, reason_options.text
    assert reason_options.json() == {
        "personal_reasons": ["现场检修领用"],
        "system_reasons": ["全员用途四", "全员用途三", "全员用途二"],
    }

    rename = await client.patch(
        f"/api/v1/mini-program-users/{created_user['id']}",
        headers=admin,
        json={
            "display_name": "管理员修改",
            "department_name": "设备保障部",
            "version": created_user["version"],
        },
    )
    assert rename.status_code == 200, rename.text
    assert rename.json()["display_name"] == "管理员修改"
    assert rename.json()["department_name"] == "设备保障部"

    repeated_login = await client.post(
        "/api/v1/mini-program/auth/wx-login",
        json={"code": "temporary-login-code"},
    )
    assert repeated_login.status_code == 200, repeated_login.text
    assert repeated_login.json()["requires_profile"] is False
    assert repeated_login.json()["registration_token"] is None
    assert repeated_login.json()["user"]["id"] == created_user["id"]
    assert repeated_login.json()["user"]["display_name"] == "管理员修改"

    disabled = await client.patch(
        f"/api/v1/mini-program-users/{created_user['id']}",
        headers=admin,
        json={"enabled": False, "version": rename.json()["version"]},
    )
    assert disabled.status_code == 200, disabled.text
    disabled_login = await client.post(
        "/api/v1/mini-program/auth/wx-login",
        json={"code": "temporary-login-code"},
    )
    assert disabled_login.status_code == 403
    assert disabled_login.json()["code"] == "ACCOUNT_DISABLED"
    assert disabled_login.json()["message"] == "您的账号已被禁用"
    disabled_request = await client.get(
        "/api/v1/mini-program/outbound-reasons", headers=mini_headers
    )
    assert disabled_request.status_code == 403
    assert disabled_request.json()["code"] == "ACCOUNT_DISABLED"

    deleted = await client.delete(
        f"/api/v1/mini-program-users/{created_user['id']}",
        headers=admin,
        params={"version": disabled.json()["version"]},
    )
    assert deleted.status_code == 204, deleted.text
    historical_operation = await client.get(
        f"/api/v1/inventory/operations/{outbound.json()['operation_id']}", headers=warehouse
    )
    assert historical_operation.status_code == 200
    assert historical_operation.json()["source_type"] == "MINI_PROGRAM"
    assert historical_operation.json()["mini_program_user_id"] is None
    assert historical_operation.json()["mini_program_user_name"] == "扫码出库员"

    login_after_delete = await client.post(
        "/api/v1/mini-program/auth/wx-login",
        json={"code": "temporary-login-code"},
    )
    assert login_after_delete.status_code == 200
    assert login_after_delete.json()["requires_profile"] is True
    rebound = await client.post(
        "/api/v1/mini-program/profile",
        headers={
            "Authorization": f"Bearer {login_after_delete.json()['registration_token']}"
        },
        json={
            "display_name": "重新绑定姓名",
            "department_name": "华星检修维护部电气车间",
        },
    )
    assert rebound.status_code == 200, rebound.text
    assert rebound.json()["user"]["display_name"] == "重新绑定姓名"
    assert rebound.json()["user"]["wechat_openid"] == "openid-for-scan-user"


@pytest.mark.asyncio
async def test_mini_program_inventory_search_filters_pagination_and_detail(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_exchange_wechat_code(code: str) -> str:
        return f"inventory-{code}"

    monkeypatch.setattr(
        mini_program_service,
        "exchange_wechat_code",
        fake_exchange_wechat_code,
    )
    warehouse = await auth_headers(client, "warehouse")
    login = await client.post(
        "/api/v1/mini-program/auth/wx-login",
        json={"code": "browser-user"},
    )
    profile = await client.post(
        "/api/v1/mini-program/profile",
        headers={"Authorization": f"Bearer {login.json()['registration_token']}"},
        json={
            "display_name": "库存浏览员",
            "department_name": "华星检修维护部电气车间",
        },
    )
    mini_headers = {"Authorization": f"Bearer {profile.json()['access_token']}"}

    source = io.BytesIO()
    Image.new("RGB", (32, 24), "blue").save(source, format="PNG")
    uploaded = await client.post(
        "/api/v1/files/images",
        headers=warehouse,
        files={"file": ("inventory.png", source.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]

    async def create_material(
        name: str, model_spec: str, *, image_ids: list[str] | None = None
    ) -> dict[str, object]:
        response = await client.post(
            "/api/v1/stock-materials",
            headers=warehouse,
            json={
                "name": name,
                "model_spec": model_spec,
                "unit_id": 1,
                "remark": f"{name}只读详情",
                "image_ids": image_ids or [],
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    no_stock = await create_material("零库存接触器", "ZERO-1", image_ids=[file_id])
    low_stock = await create_material("低库存继电器", "LOW-1")
    normal_stock = await create_material("库存充足电机", "NORMAL-1")

    for material, quantity in ((low_stock, "2"), (normal_stock, "8")):
        policy = await client.put(
            f"/api/v1/stock-materials/{material['id']}/replenishment-policy",
            headers=warehouse,
            json={"minimum_qty": "5", "enabled": True},
        )
        assert policy.status_code == 200, policy.text
        inbound = await client.post(
            "/api/v1/inventory/inbounds",
            headers=warehouse,
            json={
                "client_request_id": f"inventory-browser-{material['id']}",
                "occurred_at": "2026-07-26T09:00:00+08:00",
                "source_type": "MANUAL",
                "business_reason": "库存浏览测试",
                "lines": [{"stock_material_id": material["id"], "quantity": quantity}],
            },
        )
        assert inbound.status_code == 201, inbound.text

    first_page = await client.get(
        "/api/v1/mini-program/inventory",
        headers=mini_headers,
        params={"page": 1, "page_size": 2},
    )
    second_page = await client.get(
        "/api/v1/mini-program/inventory",
        headers=mini_headers,
        params={"page": 2, "page_size": 2},
    )
    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert len(first_page.json()["items"]) == 2
    assert len(second_page.json()["items"]) == 1
    assert set(first_page.json()["items"][0]) == {
        "uuid",
        "name",
        "model_spec",
        "unit_name",
        "current_qty",
        "stock_status",
    }

    searched = await client.get(
        "/api/v1/mini-program/inventory",
        headers=mini_headers,
        params={"keyword": "LOW-1"},
    )
    assert searched.status_code == 200
    assert [item["uuid"] for item in searched.json()["items"]] == [low_stock["uuid"]]

    empty_items = await client.get(
        "/api/v1/mini-program/inventory",
        headers=mini_headers,
        params={"stock_status": "out_of_stock"},
    )
    low_items = await client.get(
        "/api/v1/mini-program/inventory",
        headers=mini_headers,
        params={"stock_status": "low_stock"},
    )
    assert [item["uuid"] for item in empty_items.json()["items"]] == [no_stock["uuid"]]
    assert [item["uuid"] for item in low_items.json()["items"]] == [low_stock["uuid"]]

    detail = await client.get(
        f"/api/v1/mini-program/materials/{no_stock['uuid']}", headers=mini_headers
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["stock_status"] == "out_of_stock"
    assert detail.json()["remark"] == "零库存接触器只读详情"
    assert detail.json()["minimum_qty"] is None
    assert [image["id"] for image in detail.json()["images"]] == [file_id]

    write_attempt = await client.post(
        "/api/v1/mini-program/inventory",
        headers=mini_headers,
        json={"name": "不允许修改"},
    )
    assert write_attempt.status_code == 405


@pytest.mark.asyncio
async def test_advanced_setting_can_close_new_mini_program_bindings(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_exchange_wechat_code(code: str) -> str:
        return f"openid-{code}"

    monkeypatch.setattr(
        mini_program_service,
        "exchange_wechat_code",
        fake_exchange_wechat_code,
    )
    admin = await auth_headers(client, "admin")

    existing_login = await client.post(
        "/api/v1/mini-program/auth/wx-login", json={"code": "existing"}
    )
    existing_profile = await client.post(
        "/api/v1/mini-program/profile",
        headers={
            "Authorization": f"Bearer {existing_login.json()['registration_token']}"
        },
        json={
            "display_name": "已绑定用户",
            "department_name": "华星检修维护部电气车间",
        },
    )
    assert existing_profile.status_code == 200, existing_profile.text

    pending_login = await client.post(
        "/api/v1/mini-program/auth/wx-login", json={"code": "pending"}
    )
    pending_token = pending_login.json()["registration_token"]

    settings = await client.put(
        "/api/v1/ai-search/settings",
        headers=admin,
        json={
            "endpoint": "",
            "api_key": "",
            "model": "",
            "enabled": False,
            "mini_program_code_env": "release",
            "mini_program_registration_enabled": False,
            "version": 0,
        },
    )
    assert settings.status_code == 200, settings.text

    existing_again = await client.post(
        "/api/v1/mini-program/auth/wx-login", json={"code": "existing"}
    )
    assert existing_again.status_code == 200
    assert existing_again.json()["requires_profile"] is False

    new_login = await client.post(
        "/api/v1/mini-program/auth/wx-login", json={"code": "new"}
    )
    assert new_login.status_code == 403
    assert new_login.json()["code"] == "MINI_PROGRAM_REGISTRATION_DISABLED"

    stale_registration = await client.post(
        "/api/v1/mini-program/profile",
        headers={"Authorization": f"Bearer {pending_token}"},
        json={
            "display_name": "未完成绑定用户",
            "department_name": "华星检修维护部电气车间",
        },
    )
    assert stale_registration.status_code == 403
    assert stale_registration.json()["code"] == "MINI_PROGRAM_REGISTRATION_DISABLED"


@pytest.mark.asyncio
async def test_mini_program_users_require_super_admin(client: AsyncClient) -> None:
    warehouse = await auth_headers(client, "warehouse")
    response = await client.get("/api/v1/mini-program-users", headers=warehouse)
    assert response.status_code == 403
    deleted = await client.delete(
        "/api/v1/mini-program-users/1", headers=warehouse, params={"version": 1}
    )
    assert deleted.status_code == 403
