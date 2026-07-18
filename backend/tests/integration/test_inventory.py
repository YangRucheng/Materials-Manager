from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from app.core.database import engine
from tests.conftest import auth_headers, create_stock


def operation_payload(
    request_id: str,
    material_id: int,
    quantity: str,
    occurred_at: str,
    **line_extra: int,
) -> dict[str, object]:
    return {
        "client_request_id": request_id,
        "occurred_at": occurred_at,
        "source_type": "MANUAL",
        "business_reason": "测试库存业务",
        "lines": [{"stock_material_id": material_id, "quantity": quantity, **line_extra}],
    }


@pytest.mark.asyncio
async def test_inbound_reason_defaults_empty_but_outbound_still_requires_it(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client, "warehouse")
    material_id = await create_stock(client, headers, "业务原因测试")
    payload = {
        "client_request_id": "inbound-without-reason",
        "occurred_at": "2026-07-18T10:00:00+08:00",
        "source_type": "MANUAL",
        "lines": [{"stock_material_id": material_id, "quantity": "1"}],
    }
    inbound = await client.post("/api/v1/inventory/inbounds", headers=headers, json=payload)
    assert inbound.status_code == 201, inbound.text
    assert inbound.json()["business_reason"] == ""

    payload["client_request_id"] = "outbound-without-reason"
    outbound = await client.post("/api/v1/inventory/outbounds", headers=headers, json=payload)
    assert outbound.status_code == 400
    assert outbound.json()["code"] == "BUSINESS_REASON_REQUIRED"

    payload["business_reason"] = "测试出库"
    outbound = await client.post("/api/v1/inventory/outbounds", headers=headers, json=payload)
    assert outbound.status_code == 400
    assert outbound.json()["code"] == "RECEIVER_REQUIRED"


@pytest.mark.asyncio
async def test_idempotency_negative_stock_and_permissions(client: AsyncClient) -> None:
    warehouse = await auth_headers(client, "warehouse")
    readonly = await auth_headers(client, "readonly")
    forbidden = await client.post(
        "/api/v1/stock-materials",
        headers=readonly,
        json={
            "name": "无权限物资",
            "model_spec": "无",
            "unit_id": 1,
            "image_ids": [],
        },
    )
    assert forbidden.status_code == 403

    material_id = await create_stock(client, warehouse)
    payload = operation_payload("inbound-idempotent", material_id, "5", "2026-07-17T10:00:00+08:00")
    first = await client.post("/api/v1/inventory/inbounds", headers=warehouse, json=payload)
    second = await client.post("/api/v1/inventory/inbounds", headers=warehouse, json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    outbound = await client.post(
        "/api/v1/inventory/outbounds",
        headers=warehouse,
        json=operation_payload(
            "outbound-too-much", material_id, "6", "2026-07-17T11:00:00+08:00"
        )
        | {"receiver_name": "测试领用人"},
    )
    assert outbound.status_code == 201, outbound.text
    detail = await client.get(f"/api/v1/stock-materials/{material_id}", headers=warehouse)
    assert detail.json()["current_qty"] == "-1"


@pytest.mark.asyncio
async def test_edit_historical_operation_replays_snapshots(client: AsyncClient) -> None:
    headers = await auth_headers(client, "warehouse")
    material_id = await create_stock(client, headers)
    inbound = await client.post(
        "/api/v1/inventory/inbounds",
        headers=headers,
        json=operation_payload("history-in", material_id, "10", "2026-07-17T10:00:00+08:00"),
    )
    outbound = await client.post(
        "/api/v1/inventory/outbounds",
        headers=headers,
        json=operation_payload("history-out", material_id, "3", "2026-07-18T10:00:00+08:00")
        | {"receiver_name": "测试领用人"},
    )
    assert inbound.status_code == outbound.status_code == 201

    changed = await client.patch(
        f"/api/v1/inventory/operations/{inbound.json()['id']}",
        headers=headers,
        json={
            "version": inbound.json()["version"],
            "operation_type": "INBOUND",
            "occurred_at": "2026-07-17T10:00:00+08:00",
            "source_type": "MANUAL",
            "business_reason": "历史入库改为 5",
            "lines": [{"stock_material_id": material_id, "quantity": "5"}],
        },
    )
    assert changed.status_code == 200, changed.text
    later = await client.get(
        f"/api/v1/inventory/operations/{outbound.json()['id']}", headers=headers
    )
    assert later.json()["lines"][0]["before_qty"] == "5"
    assert later.json()["lines"][0]["after_qty"] == "2"

    changed_again = await client.patch(
        f"/api/v1/inventory/operations/{changed.json()['id']}",
        headers=headers,
        json={
            "version": changed.json()["version"],
            "operation_type": "INBOUND",
            "occurred_at": "2026-07-17T10:00:00+08:00",
            "source_type": "MANUAL",
            "business_reason": "会造成负库存",
            "lines": [{"stock_material_id": material_id, "quantity": "2"}],
        },
    )
    assert changed_again.status_code == 200, changed_again.text
    later = await client.get(
        f"/api/v1/inventory/operations/{outbound.json()['id']}", headers=headers
    )
    assert later.json()["lines"][0]["before_qty"] == "2"
    assert later.json()["lines"][0]["after_qty"] == "-1"
    detail = await client.get(f"/api/v1/stock-materials/{material_id}", headers=headers)
    assert detail.json()["current_qty"] == "-1"


@pytest.mark.asyncio
async def test_concurrent_outbound_allows_negative_without_lost_updates(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client, "warehouse")
    material_id = await create_stock(client, headers)
    await client.post(
        "/api/v1/inventory/inbounds",
        headers=headers,
        json=operation_payload("concurrent-in", material_id, "5", "2026-07-17T10:00:00+08:00"),
    )

    async def outbound(request_id: str):
        return await client.post(
            "/api/v1/inventory/outbounds",
            headers=headers,
            json=operation_payload(request_id, material_id, "4", "2026-07-17T11:00:00+08:00")
            | {"receiver_name": "测试领用人"},
        )

    if engine.dialect.name == "mysql":
        # MySQL/InnoDB 分支验证 SELECT ... FOR UPDATE 串行化后不会丢失扣减。
        responses = await asyncio.gather(outbound("concurrent-a"), outbound("concurrent-b"))
    else:
        # SQLite 不提供行级 FOR UPDATE；本地快速测试顺序执行相同业务。
        responses = [await outbound("concurrent-a"), await outbound("concurrent-b")]
    assert [response.status_code for response in responses] == [201, 201]
    detail = await client.get(f"/api/v1/stock-materials/{material_id}", headers=headers)
    assert detail.json()["current_qty"] == "-3"


@pytest.mark.asyncio
async def test_low_stock_on_order_calculation_and_disabled_material(client: AsyncClient) -> None:
    warehouse = await auth_headers(client, "warehouse")
    purchase = await auth_headers(client, "purchase")
    material_id = await create_stock(client, warehouse, "低库存物资")
    policy = await client.put(
        f"/api/v1/stock-materials/{material_id}/replenishment-policy",
        headers=warehouse,
        json={"minimum_qty": "3", "target_qty": "10", "enabled": True},
    )
    assert policy.status_code == 200
    low = await client.get("/api/v1/inventory/low-stock", headers=warehouse)
    assert low.json()["items"][0]["warning_state"] == "PENDING_PURCHASE"
    assert low.json()["items"][0]["suggested_purchase_qty"] == "10"

    replenishment = await client.post(
        f"/api/v1/inventory/low-stock/{material_id}/create-replenishment-draft",
        headers=warehouse,
    )
    assert replenishment.status_code == 200, replenishment.text
    assert replenishment.json()["next"] == "purchase_material"
    plan = await client.get(
        f"/api/v1/purchase-materials/{replenishment.json()['resource_id']}", headers=purchase
    )
    assert plan.json()["stock_material_id"] == material_id
    requests = await client.get("/api/v1/purchase-requests", headers=purchase)
    assert requests.json()["total"] == 0

    purchase_material = await client.post(
        "/api/v1/purchase-materials",
        headers=purchase,
        json={
            "material_code": "DQ-LOW-001",
            "name": "低库存物资",
            "model_spec": "CJX2-2510 220V",
            "unit_id": 1,
            "purchase_responsible": "李工",
            "planned_qty": "5",
            "usage": "低库存补库",
            "subitem_no": "01-01",
            "stock_material_id": material_id,
            "image_ids": [],
        },
    )
    request = await client.post(
        "/api/v1/purchase-requests",
        headers=purchase,
        json={
            "lines": [
                {
                    "purchase_material_id": purchase_material.json()["id"],
                    "requested_qty": "5",
                    "usage": "低库存补库",
                    "subitem_no": "01-01",
                }
            ]
        },
    )
    await client.post(
        f"/api/v1/purchase-requests/{request.json()['id']}/submit",
        headers=purchase,
        json={},
    )
    low = await client.get("/api/v1/inventory/low-stock", headers=warehouse)
    assert low.json()["items"][0]["warning_state"] == "ON_ORDER"
    assert low.json()["items"][0]["on_order_qty"] == "5"
    assert low.json()["items"][0]["suggested_purchase_qty"] == "5"

    disabled = await client.post(
        f"/api/v1/stock-materials/{material_id}/disable", headers=warehouse, json={}
    )
    assert disabled.status_code == 200
    rejected = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json=operation_payload("disabled-inbound", material_id, "1", "2026-07-17T10:00:00+08:00"),
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "MATERIAL_DISABLED"
