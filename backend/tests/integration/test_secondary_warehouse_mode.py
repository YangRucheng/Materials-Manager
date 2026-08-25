from __future__ import annotations

import asyncio
import csv
from io import BytesIO, StringIO

import pytest
from httpx import AsyncClient
from openpyxl import Workbook

from app.services import mini_program_service
from tests.conftest import auth_headers, create_stock

LITE_HEADERS = ["物资名称", "型号规格", "单位", "数量", "备注"]


def build_lite_report(rows: list[list[object]]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(LITE_HEADERS)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


async def _set_mode(client: AsyncClient, admin: dict[str, str], mode: str) -> int:
    current = await client.get("/api/v1/ai-search/settings", headers=admin)
    assert current.status_code == 200, current.text
    version = current.json()["version"]
    settings = await client.put(
        "/api/v1/ai-search/settings",
        headers=admin,
        json={
            "endpoint": "",
            "api_key": "",
            "model": "",
            "enabled": False,
            "secondary_warehouse_mode": mode,
            "version": version,
        },
    )
    assert settings.status_code == 200, settings.text
    assert settings.json()["secondary_warehouse_mode"] == mode
    return settings.json()["version"]


async def _import_lite(
    client: AsyncClient, headers: dict[str, str], rows: list[list[object]]
) -> None:
    response = await client.post(
        "/api/v1/secondary-warehouse/import",
        headers=headers,
        files={"file": ("lite.csv", build_lite_report(rows), "application/octet-stream")},
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    for _ in range(200):
        job = await client.get(
            f"/api/v1/secondary-warehouse/import-jobs/{job_id}", headers=headers
        )
        if job.status_code == 200 and job.json()["status"] in ("SUCCEEDED", "FAILED"):
            assert job.json()["status"] == "SUCCEEDED", job.text
            return
        await asyncio.sleep(0.05)
    raise AssertionError("lite import job did not finish in time")


@pytest.mark.asyncio
async def test_features_endpoint_exposes_secondary_warehouse_mode(
    client: AsyncClient,
) -> None:
    features = await client.get("/api/v1/system-settings/mini-program-features")
    assert features.status_code == 200
    # 未配置时默认完整模式
    assert features.json()["secondary_warehouse_mode"] == "full"


@pytest.mark.asyncio
async def test_settings_roundtrip_persists_mode(client: AsyncClient) -> None:
    admin = await auth_headers(client, "admin")
    version = await _set_mode(client, admin, "lite")

    read = await client.get("/api/v1/ai-search/settings", headers=admin)
    assert read.status_code == 200, read.text
    assert read.json()["secondary_warehouse_mode"] == "lite"
    assert read.json()["version"] == version

    features = await client.get("/api/v1/system-settings/mini-program-features")
    assert features.json()["secondary_warehouse_mode"] == "lite"


@pytest.mark.asyncio
async def test_lite_mode_blocks_mini_program_outbound(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_exchange_wechat_code(
        code: str, app_id: str | None = None
    ) -> tuple[str, str]:
        return app_id or "wx-test-primary", f"openid-{code}"

    monkeypatch.setattr(
        mini_program_service,
        "exchange_wechat_code",
        fake_exchange_wechat_code,
    )
    admin = await auth_headers(client, "admin")
    warehouse = await auth_headers(client, "warehouse")

    login = await client.post("/api/v1/mini-program/auth/wx-login", json={"code": "lite"})
    assert login.status_code == 200, login.text
    profile = await client.post(
        "/api/v1/mini-program/profile",
        headers={"Authorization": f"Bearer {login.json()['registration_token']}"},
        json={"display_name": "精简用户", "department_name": "华星检修维护部电气车间"},
    )
    assert profile.status_code == 200, profile.text
    mini_headers = {"Authorization": f"Bearer {profile.json()['access_token']}"}

    material_id = await create_stock(client, warehouse, "精简模式测试物资")

    await _set_mode(client, admin, "lite")

    reasons = await client.get("/api/v1/mini-program/outbound-reasons", headers=mini_headers)
    assert reasons.status_code == 403
    assert reasons.json()["code"] == "OUTBOUND_DISABLED"

    outbound = await client.post(
        "/api/v1/mini-program/outbound",
        headers=mini_headers,
        json={
            "client_request_id": "lite-outbound-1",
            "material_uuid": (
                await client.get(
                    f"/api/v1/stock-materials/{material_id}", headers=warehouse
                )
            ).json()["uuid"],
            "occurred_at": "2026-01-01T08:00:00+08:00",
            "quantity": 1,
            "business_reason": "测试",
            "subitem_no": "201-1",
        },
    )
    assert outbound.status_code == 403
    assert outbound.json()["code"] == "OUTBOUND_DISABLED"


@pytest.mark.asyncio
async def test_lite_mode_blocks_admin_full_warehouse_writes(client: AsyncClient) -> None:
    admin = await auth_headers(client, "admin")
    warehouse = await auth_headers(client, "warehouse")

    # 完整模式（默认）允许写入
    created = await client.post(
        "/api/v1/stock-materials",
        headers=warehouse,
        json={"name": "完整模式物资", "model_spec": "FULL-1", "unit_name": "个", "image_ids": []},
    )
    assert created.status_code == 201, created.text

    await _set_mode(client, admin, "lite")

    blocked = await client.post(
        "/api/v1/stock-materials",
        headers=warehouse,
        json={"name": "精简模式不应创建", "model_spec": "LITE-1", "unit_name": "个", "image_ids": []},
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "SECONDARY_WAREHOUSE_LITE_MODE"

    inbound = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json={
            "client_request_id": "lite-inbound-1",
            "occurred_at": "2026-01-01T08:00:00+08:00",
            "source_type": "MANUAL",
            "business_reason": "测试",
            "lines": [{"stock_material_id": created.json()["id"], "quantity": 1}],
        },
    )
    assert inbound.status_code == 403
    assert inbound.json()["code"] == "SECONDARY_WAREHOUSE_LITE_MODE"


@pytest.mark.asyncio
async def test_lite_mode_mini_program_lite_inventory(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_exchange_wechat_code(
        code: str, app_id: str | None = None
    ) -> tuple[str, str]:
        return app_id or "wx-test-primary", f"openid-{code}"

    monkeypatch.setattr(
        mini_program_service,
        "exchange_wechat_code",
        fake_exchange_wechat_code,
    )
    admin = await auth_headers(client, "admin")
    warehouse = await auth_headers(client, "warehouse")

    await _set_mode(client, admin, "lite")
    await _import_lite(
        client, warehouse, [["精简接触器", "CJX2-2510", "个", 8, "备注"]]
    )

    login = await client.post("/api/v1/mini-program/auth/wx-login", json={"code": "lite"})
    profile = await client.post(
        "/api/v1/mini-program/profile",
        headers={"Authorization": f"Bearer {login.json()['registration_token']}"},
        json={"display_name": "精简用户", "department_name": "华星检修维护部电气车间"},
    )
    mini_headers = {"Authorization": f"Bearer {profile.json()['access_token']}"}

    listed = await client.get(
        "/api/v1/mini-program/lite-inventory", headers=mini_headers, params={"page_size": 50}
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    item = listed.json()["items"][0]
    assert item["name"] == "精简接触器"
    assert item["quantity"] == "8"

    last_import = await client.get(
        "/api/v1/mini-program/lite-inventory/last-import", headers=mini_headers
    )
    assert last_import.status_code == 200
    assert last_import.json()["last_import_at"] is not None


@pytest.mark.asyncio
async def test_lite_mode_dashboard_summary_counts_lite_inventory(
    client: AsyncClient,
) -> None:
    admin = await auth_headers(client, "admin")
    warehouse = await auth_headers(client, "warehouse")

    # 完整模式默认工作台统计完整模式物资
    await create_stock(client, warehouse, "完整物资A")
    await create_stock(client, warehouse, "完整物资B")
    full_summary = await client.get("/api/v1/dashboard/summary", headers=admin)
    assert full_summary.status_code == 200, full_summary.text
    assert full_summary.json()["stock_material_count"] == 2

    await _set_mode(client, admin, "lite")
    await _import_lite(client, warehouse, [["精简物资A", "M1", "个", 1, ""]])

    lite_summary = await client.get("/api/v1/dashboard/summary", headers=admin)
    assert lite_summary.status_code == 200, lite_summary.text
    assert lite_summary.json()["stock_material_count"] == 1
    assert lite_summary.json()["low_stock_count"] == 0
