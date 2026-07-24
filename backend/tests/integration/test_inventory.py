from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta, timezone

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
        json=operation_payload("outbound-too-much", material_id, "6", "2026-07-17T11:00:00+08:00")
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
    assert changed.json()["lines"][0]["id"] == inbound.json()["lines"][0]["id"]
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

    changed_outbound = await client.patch(
        f"/api/v1/inventory/operations/{outbound.json()['id']}",
        headers=headers,
        json={
            "version": outbound.json()["version"],
            "operation_type": "OUTBOUND",
            "occurred_at": "2026-07-18T10:00:00+08:00",
            "source_type": "MANUAL",
            "business_reason": "扩大负库存",
            "receiver_name": "测试领用人",
            "lines": [{"stock_material_id": material_id, "quantity": "5"}],
        },
    )
    assert changed_outbound.status_code == 200, changed_outbound.text
    assert changed_outbound.json()["lines"][0]["id"] == outbound.json()["lines"][0]["id"]
    assert changed_outbound.json()["lines"][0]["before_qty"] == "2"
    assert changed_outbound.json()["lines"][0]["after_qty"] == "-3"
    detail = await client.get(f"/api/v1/stock-materials/{material_id}", headers=headers)
    assert detail.json()["current_qty"] == "-3"


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
async def test_low_stock_replenishment_uses_recent_consumption_and_defaults(
    client: AsyncClient,
) -> None:
    warehouse = await auth_headers(client, "warehouse")
    purchase = await auth_headers(client, "purchase")
    material_id = await create_stock(client, warehouse, "低库存物资")
    latest_plan = await client.post(
        "/api/v1/purchase-materials",
        headers=purchase,
        json={
            "plan_date": "2026-07-20",
            "name": "负责人默认值样本",
            "model_spec": "无",
            "unit_id": 1,
            "actual_demand_person": "检修班",
            "purchase_responsible": "最近负责人王工",
            "planned_qty": "1",
            "usage": "测试默认值",
            "image_ids": [],
        },
    )
    assert latest_plan.status_code == 201, latest_plan.text
    defaults = await client.get("/api/v1/inventory/replenishment-defaults", headers=warehouse)
    assert defaults.status_code == 200, defaults.text
    assert defaults.json()["purchase_responsible"] == "最近负责人王工"
    shanghai = timezone(timedelta(hours=8))
    assert defaults.json()["demand_date"] == datetime.now(shanghai).date().isoformat()

    now = datetime.now(UTC)
    recent_outbound = await client.post(
        "/api/v1/inventory/outbounds",
        headers=warehouse,
        json=operation_payload(
            "recent-consumption", material_id, "5", (now - timedelta(days=30)).isoformat()
        )
        | {"receiver_name": "近期领用人"},
    )
    assert recent_outbound.status_code == 201, recent_outbound.text
    old_outbound = await client.post(
        "/api/v1/inventory/outbounds",
        headers=warehouse,
        json=operation_payload(
            "old-consumption", material_id, "7", (now - timedelta(days=220)).isoformat()
        )
        | {"receiver_name": "历史领用人"},
    )
    assert old_outbound.status_code == 201, old_outbound.text
    policy = await client.put(
        f"/api/v1/stock-materials/{material_id}/replenishment-policy",
        headers=warehouse,
        json={"minimum_qty": "3", "enabled": True},
    )
    assert policy.status_code == 200
    assert "target_qty" not in policy.json()["replenishment_policy"]
    low = await client.get("/api/v1/inventory/low-stock", headers=warehouse)
    assert low.json()["items"][0]["suggested_purchase_qty"] == "5"
    assert "target_qty" not in low.json()["items"][0]
    assert "warning_state" not in low.json()["items"][0]
    assert "on_order_qty" not in low.json()["items"][0]

    missing_confirmation = await client.post(
        f"/api/v1/inventory/low-stock/{material_id}/create-replenishment-draft",
        headers=warehouse,
        json={},
    )
    assert missing_confirmation.status_code == 422

    additional_outbound = await client.post(
        "/api/v1/inventory/outbounds",
        headers=warehouse,
        json=operation_payload(
            "latest-consumption", material_id, "2", (now - timedelta(days=1)).isoformat()
        )
        | {"receiver_name": "最新领用人"},
    )
    assert additional_outbound.status_code == 201, additional_outbound.text
    low = await client.get("/api/v1/inventory/low-stock", headers=warehouse)
    assert low.json()["items"][0]["suggested_purchase_qty"] == "7"

    demand_date = (now.date() + timedelta(days=10)).isoformat()
    replenishment = await client.post(
        f"/api/v1/inventory/low-stock/{material_id}/create-replenishment-draft",
        headers=warehouse,
        json={
            "planned_qty": "9",
            "demand_date": demand_date,
            "actual_demand_person": "检修班张三",
            "purchase_responsible": "自定义负责人李工",
        },
    )
    assert replenishment.status_code == 200, replenishment.text
    assert replenishment.json()["next"] == "purchase_material"
    plan = await client.get(
        f"/api/v1/purchase-materials/{replenishment.json()['resource_id']}", headers=purchase
    )
    assert plan.json()["stock_material_id"] == material_id
    assert plan.json()["planned_qty"] == "9"
    assert plan.json()["plan_date"] == demand_date
    assert plan.json()["actual_demand_person"] == "检修班张三"
    assert plan.json()["purchase_responsible"] == "自定义负责人李工"
    low = await client.get("/api/v1/inventory/low-stock", headers=warehouse)
    assert low.json()["items"][0]["suggested_purchase_qty"] == "7"


@pytest.mark.asyncio
async def test_stock_material_search_supports_or_terms(client: AsyncClient) -> None:
    headers = await auth_headers(client, "warehouse")
    first_id = await create_stock(client, headers, "交流接触器")
    second = await client.post(
        "/api/v1/stock-materials",
        headers=headers,
        json={
            "name": "温度传感器",
            "model_spec": "PT100",
            "unit_id": 1,
            "remark": "测试 OR 查询",
            "image_ids": [],
        },
    )
    assert second.status_code == 201, second.text

    materials = await client.get(
        "/api/v1/stock-materials", headers=headers, params={"keyword": "交流|PT100"}
    )
    assert materials.status_code == 200, materials.text
    assert {item["id"] for item in materials.json()["items"]} == {
        first_id,
        second.json()["id"],
    }

    balances = await client.get(
        "/api/v1/inventory/balances", headers=headers, params={"keyword": "交流｜PT100"}
    )
    assert balances.status_code == 200, balances.text
    assert {item["stock_material_id"] for item in balances.json()["items"]} == {
        first_id,
        second.json()["id"],
    }


@pytest.mark.asyncio
async def test_stock_material_delete_requires_no_operation_records(client: AsyncClient) -> None:
    headers = await auth_headers(client, "warehouse")
    deletable_id = await create_stock(client, headers, "可删除物资")
    deletable = await client.get(f"/api/v1/stock-materials/{deletable_id}", headers=headers)
    assert deletable.status_code == 200, deletable.text
    assert deletable.json()["has_operation_records"] is False

    deleted = await client.delete(
        f"/api/v1/stock-materials/{deletable_id}",
        headers=headers,
        params={"version": deletable.json()["version"]},
    )
    assert deleted.status_code == 204, deleted.text
    missing = await client.get(f"/api/v1/stock-materials/{deletable_id}", headers=headers)
    assert missing.status_code == 400
    assert missing.json()["code"] == "NOT_FOUND"

    protected_id = await create_stock(client, headers, "有操作记录物资")
    inbound = await client.post(
        "/api/v1/inventory/inbounds",
        headers=headers,
        json=operation_payload(
            "delete-protected-material",
            protected_id,
            "1",
            "2026-07-24T10:00:00+08:00",
        ),
    )
    assert inbound.status_code == 201, inbound.text
    protected = await client.get(f"/api/v1/stock-materials/{protected_id}", headers=headers)
    assert protected.status_code == 200, protected.text
    assert protected.json()["has_operation_records"] is True

    rejected = await client.delete(
        f"/api/v1/stock-materials/{protected_id}",
        headers=headers,
        params={"version": protected.json()["version"]},
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "STOCK_MATERIAL_IN_USE"
