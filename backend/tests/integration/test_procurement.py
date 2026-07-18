from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_stock


async def create_purchase_material(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    code: str | None = None,
    stock_material_id: int | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/purchase-materials",
        headers=headers,
        json={
            "material_code": code,
            "name": name,
            "model_spec": "M60-2P 5A",
            "unit_id": 1,
            "remark": "新物资",
            "stock_material_id": stock_material_id,
            "image_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_request(
    client: AsyncClient,
    headers: dict[str, str],
    purchase_material_id: int,
    qty: str = "5",
    request_no: str | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/purchase-requests",
        headers=headers,
        json={
            "request_no": request_no,
            "remark": "检修备件",
            "lines": [
                {
                    "purchase_material_id": purchase_material_id,
                    "requested_qty": qty,
                    "usage": "控制柜检修",
                    "project_subitem_id": 1,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_uncoded_query_request_number_and_submit_guard(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    material = await create_purchase_material(client, headers, "未编码物资")

    uncoded = await client.get("/api/v1/purchase-materials?coded=false", headers=headers)
    assert uncoded.status_code == 200
    assert [item["id"] for item in uncoded.json()["items"]] == [material["id"]]

    request = await create_request(client, headers, int(material["id"]))
    assert request["request_no"].startswith("申购单-")
    assert request["request_no"].endswith("日")

    renamed = await client.patch(
        f"/api/v1/purchase-requests/{request['id']}",
        headers=headers,
        json={
            "version": request["version"],
            "request_no": "公司系统申购单-2026-0717-A",
            "remark": request["remark"],
            "lines": [
                {
                    "id": request["lines"][0]["id"],
                    "purchase_material_id": material["id"],
                    "requested_qty": "5",
                    "usage": "控制柜检修",
                    "project_subitem_id": 1,
                }
            ],
        },
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["request_no"] == "公司系统申购单-2026-0717-A"

    response = await client.post(
        f"/api/v1/purchase-requests/{request['id']}/submit", headers=headers, json={}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "MATERIAL_CODE_REQUIRED"
    assert response.json()["details"]["lines"][0]["purchase_material_id"] == material["id"]


@pytest.mark.asyncio
async def test_direct_code_maintenance_and_over_receipt_close_loop(client: AsyncClient) -> None:
    purchase = await auth_headers(client, "purchase")
    warehouse = await auth_headers(client, "warehouse")
    material = await create_purchase_material(client, purchase, "智能电机保护器")
    coded = await client.patch(
        f"/api/v1/purchase-materials/{material['id']}",
        headers=purchase,
        json={
            "version": material["version"],
            "material_code": "DQ-000500",
            "name": material["name"],
            "model_spec": material["model_spec"],
            "unit_id": material["unit_id"],
            "remark": material["remark"],
            "stock_material_id": None,
            "image_ids": [],
        },
    )
    assert coded.status_code == 200, coded.text
    assert coded.json()["code_state"] == "CODED"

    request = await create_request(
        client, purchase, int(material["id"]), request_no="公司请购单-DQ-2026-001"
    )
    for action in ("submit", "accept"):
        response = await client.post(
            f"/api/v1/purchase-requests/{request['id']}/{action}", headers=purchase, json={}
        )
        assert response.status_code == 200, response.text
        request = response.json()
    stock_id = await create_stock(client, warehouse, "智能电机保护器")
    line_id = request["lines"][0]["id"]

    def receipt_payload(request_id: str, quantity: str) -> dict[str, object]:
        return {
            "client_request_id": request_id,
            "occurred_at": "2026-07-17T10:00:00+08:00",
            "source_type": "PURCHASE_RECEIPT",
            "business_reason": "请购物资到货",
            "lines": [
                {
                    "stock_material_id": stock_id,
                    "quantity": quantity,
                    "purchase_request_line_id": line_id,
                }
            ],
        }

    partial = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json=receipt_payload("receipt-1", "2"),
    )
    assert partial.status_code == 201, partial.text
    full = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json=receipt_payload("receipt-2", "3"),
    )
    assert full.status_code == 201, full.text

    over = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json=receipt_payload("receipt-over", "1"),
    )
    assert over.status_code == 201, over.text
    request_state = await client.get(f"/api/v1/purchase-requests/{request['id']}", headers=purchase)
    assert request_state.json()["status"] == "COMPLETED"
    assert request_state.json()["lines"][0]["received_qty"] == "6.000"

    linked = await client.get(f"/api/v1/purchase-materials/{material['id']}", headers=purchase)
    assert linked.json()["stock_material_id"] == stock_id

    edited_receipt = await client.patch(
        f"/api/v1/inventory/operations/{partial.json()['id']}",
        headers=warehouse,
        json={
            "version": partial.json()["version"],
            "operation_type": "INBOUND",
            "occurred_at": "2026-07-17T10:00:00+08:00",
            "source_type": "PURCHASE_RECEIPT",
            "business_reason": "到货数量复核改为 1",
            "lines": [
                {
                    "stock_material_id": stock_id,
                    "quantity": "1",
                    "purchase_request_line_id": line_id,
                }
            ],
        },
    )
    assert edited_receipt.status_code == 200, edited_receipt.text
    request_state = await client.get(f"/api/v1/purchase-requests/{request['id']}", headers=purchase)
    assert request_state.json()["status"] == "COMPLETED"
    assert request_state.json()["lines"][0]["received_qty"] == "5.000"

    reversed_receipt = await client.post(
        f"/api/v1/inventory/operations/{full.json()['id']}/reverse",
        headers=warehouse,
        json={"client_request_id": "reverse-receipt-2", "reason": "到货退回"},
    )
    assert reversed_receipt.status_code == 200, reversed_receipt.text
    request_state = await client.get(f"/api/v1/purchase-requests/{request['id']}", headers=purchase)
    assert request_state.json()["status"] == "PARTIALLY_RECEIVED"
    assert request_state.json()["lines"][0]["received_qty"] == "2.000"


@pytest.mark.asyncio
async def test_purchase_plans_can_repeat_code_and_stock_material(client: AsyncClient) -> None:
    purchase = await auth_headers(client, "purchase")
    warehouse = await auth_headers(client, "warehouse")
    stock_id = await create_stock(client, warehouse, "重复补库物资")
    first = await create_purchase_material(
        client, purchase, "重复补库物资", code="DQ-REPEAT", stock_material_id=stock_id
    )
    second = await create_purchase_material(
        client, purchase, "重复补库物资", code="DQ-REPEAT", stock_material_id=stock_id
    )
    assert first["id"] != second["id"]
