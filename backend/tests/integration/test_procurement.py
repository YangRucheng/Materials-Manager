from __future__ import annotations

from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook

from app.core.config import settings
from tests.conftest import auth_headers, create_stock


async def create_purchase_plan(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    code: str | None = None,
    stock_material_id: int | None = None,
    planned_qty: str = "5",
    purchase_responsible: str = "李工",
    subitem_no: str | None = "01-01",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/purchase-materials",
        headers=headers,
        json={
            "material_code": code,
            "name": name,
            "model_spec": "M60-2P 5A",
            "unit_id": 1,
            "actual_demand_person": "车间员工张三",
            "purchase_responsible": purchase_responsible,
            "planned_qty": planned_qty,
            "usage": "控制柜检修",
            "subitem_no": subitem_no,
            "remark": "新计划",
            "stock_material_id": stock_material_id,
            "image_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["planned_qty"] == planned_qty
    assert result["purchase_responsible"] == purchase_responsible
    assert "code_state" not in result
    return result


async def move_to_record(
    client: AsyncClient,
    headers: dict[str, str],
    plan_id: int,
    trace_no: str = "ZS-2026-001",
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/purchase-materials/{plan_id}/move-to-record",
        headers=headers,
        json={
            "purchase_order_no": "SG-2026-001",
            "trace_no": trace_no,
            "purchase_date": "2026-07-18",
            "salesperson": "赵经理",
            "remark": "等待供应商发货",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_uncoded_plan_must_be_coded_before_moving_to_record(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "未编码物资")

    uncoded = await client.get("/api/v1/purchase-materials?coded=false", headers=headers)
    assert uncoded.status_code == 200
    assert [item["id"] for item in uncoded.json()["items"]] == [plan["id"]]

    rejected = await client.post(
        f"/api/v1/purchase-materials/{plan['id']}/move-to-record",
        headers=headers,
        json={
            "purchase_order_no": "SG-UNCODED",
            "trace_no": "ZS-UNCODED",
            "purchase_date": "2026-07-18",
        },
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "MATERIAL_CODE_REQUIRED"

    coded = await client.patch(
        f"/api/v1/purchase-materials/{plan['id']}",
        headers=headers,
        json={
            "version": plan["version"],
            "material_code": "DQ-000500",
            "name": plan["name"],
            "model_spec": plan["model_spec"],
            "unit_id": plan["unit_id"],
            "actual_demand_person": plan["actual_demand_person"],
            "purchase_responsible": plan["purchase_responsible"],
            "planned_qty": plan["planned_qty"],
            "usage": plan["usage"],
            "subitem_no": plan["subitem_no"],
            "remark": plan["remark"],
            "stock_material_id": None,
            "image_ids": [],
        },
    )
    assert coded.status_code == 200, coded.text
    record = await move_to_record(client, headers, int(plan["id"]))
    assert record["material_code"] == "DQ-000500"
    assert record["planned_qty"] == "5"
    assert record["status"] == "PROCESSING"


@pytest.mark.asyncio
async def test_plan_allows_optional_subitem_and_manual_stock_link(client: AsyncClient) -> None:
    purchase = await auth_headers(client, "purchase")
    warehouse = await auth_headers(client, "warehouse")
    stock_id = await create_stock(client, warehouse, "手动关联物资")

    plan = await create_purchase_plan(
        client,
        purchase,
        "手动关联物资",
        code="DQ-LINK-001",
        stock_material_id=stock_id,
        subitem_no=None,
    )

    assert plan["subitem_no"] is None
    assert plan["stock_material_id"] == stock_id
    assert plan["stock_material_name"] == "手动关联物资"
    record = await move_to_record(client, purchase, int(plan["id"]), "无子项申购")
    assert record["subitem_no"] is None


@pytest.mark.asyncio
async def test_plan_can_be_deleted_until_moved_to_record(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    deletable = await create_purchase_plan(client, headers, "待删除计划")
    deleted = await client.delete(
        f"/api/v1/purchase-materials/{deletable['id']}",
        headers=headers,
        params={"version": deletable["version"]},
    )
    assert deleted.status_code == 204, deleted.text
    missing = await client.get(f"/api/v1/purchase-materials/{deletable['id']}", headers=headers)
    assert missing.status_code == 400

    moved = await create_purchase_plan(client, headers, "已转入计划", code="DQ-MOVED")
    await move_to_record(client, headers, int(moved["id"]))
    rejected = await client.delete(
        f"/api/v1/purchase-materials/{moved['id']}",
        headers=headers,
        params={"version": moved["version"]},
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "PURCHASE_PLAN_IN_USE"


@pytest.mark.asyncio
async def test_multiple_plans_can_move_to_one_purchase_record_batch(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    first = await create_purchase_plan(client, headers, "批量计划一", code="DQ-BATCH-1")
    second = await create_purchase_plan(
        client,
        headers,
        "批量计划二",
        code="DQ-BATCH-2",
        purchase_responsible="另一负责人",
    )
    response = await client.post(
        "/api/v1/purchase-materials/batch-move-to-record",
        headers=headers,
        json={
            "material_ids": [first["id"], second["id"]],
            "purchase_order_no": "SG-BATCH-001",
            "trace_no": "ZS-BATCH-001",
            "purchase_date": "2026-07-18",
            "salesperson": "批量业务员",
            "remark": "批量转入",
        },
    )
    assert response.status_code == 200, response.text
    records = response.json()
    assert len(records) == 2
    assert {record["purchase_material_id"] for record in records} == {
        first["id"],
        second["id"],
    }
    assert len({record["purchase_request_id"] for record in records}) == 1
    assert {record["trace_no"] for record in records} == {"ZS-BATCH-001"}
    assert {record["purchase_order_no"] for record in records} == {"SG-BATCH-001"}


@pytest.mark.asyncio
async def test_flat_purchase_records_support_tracking_fields(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    first = await create_purchase_plan(
        client, headers, "负责人一", code="DQ-1", purchase_responsible="外部负责人甲"
    )
    second = await create_purchase_plan(
        client, headers, "负责人二", code="DQ-2", purchase_responsible="外部负责人乙"
    )
    first_record = await move_to_record(client, headers, int(first["id"]), "正式申购-A")
    await move_to_record(client, headers, int(second["id"]), "正式申购-B")

    remaining_plans = await client.get("/api/v1/purchase-materials?moved=false", headers=headers)
    assert remaining_plans.json()["total"] == 0

    records = await client.get("/api/v1/purchase-records", headers=headers)
    assert records.status_code == 200
    assert records.json()["total"] == 2
    assert len(records.json()["items"]) == 2
    assert all("material_name" in item for item in records.json()["items"])

    changed = await client.patch(
        f"/api/v1/purchase-records/{first_record['line_id']}",
        headers=headers,
        json={
            "version": first_record["version"],
            "purchase_order_no": "SG-A-修订",
            "trace_no": "ZS-A-修订",
            "purchase_date": "2026-07-19",
            "salesperson": "钱经理",
            "remark": "预计下周到货",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["trace_no"] == "ZS-A-修订"
    assert changed.json()["purchase_order_no"] == "SG-A-修订"
    assert changed.json()["purchase_date"] == "2026-07-19"
    assert changed.json()["salesperson"] == "钱经理"
    assert changed.json()["remark"] == "预计下周到货"

    duplicate = await client.post(
        f"/api/v1/purchase-materials/{first['id']}/move-to-record",
        headers=headers,
        json={
            "purchase_order_no": "SG-REPEAT",
            "trace_no": "ZS-REPEAT",
            "purchase_date": "2026-07-18",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "PLAN_ALREADY_MOVED"


@pytest.mark.asyncio
async def test_record_receipts_update_flat_arrival_progress(client: AsyncClient) -> None:
    purchase = await auth_headers(client, "purchase")
    warehouse = await auth_headers(client, "warehouse")
    stock_id = await create_stock(client, warehouse, "智能电机保护器")
    plan = await create_purchase_plan(
        client,
        purchase,
        "智能电机保护器",
        code="DQ-000501",
        stock_material_id=stock_id,
        planned_qty="5",
    )
    record = await move_to_record(client, purchase, int(plan["id"]))

    def receipt_payload(request_id: str, quantity: str) -> dict[str, object]:
        return {
            "client_request_id": request_id,
            "occurred_at": "2026-07-17T10:00:00+08:00",
            "source_type": "PURCHASE_RECEIPT",
            "business_reason": "",
            "lines": [
                {
                    "stock_material_id": stock_id,
                    "quantity": quantity,
                    "purchase_request_line_id": record["line_id"],
                }
            ],
        }

    partial = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json=receipt_payload("receipt-1", "2"),
    )
    assert partial.status_code == 201, partial.text
    progress = await client.get(f"/api/v1/purchase-records/{record['line_id']}", headers=purchase)
    assert progress.json()["received_qty"] == "2"
    assert progress.json()["remaining_qty"] == "3"
    assert progress.json()["status"] == "PARTIALLY_RECEIVED"

    full = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json=receipt_payload("receipt-2", "3"),
    )
    assert full.status_code == 201, full.text
    progress = await client.get(f"/api/v1/purchase-records/{record['line_id']}", headers=purchase)
    assert progress.json()["received_qty"] == "5"
    assert progress.json()["remaining_qty"] == "0"
    assert progress.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_purchase_plans_can_repeat_code_and_stock_material(client: AsyncClient) -> None:
    purchase = await auth_headers(client, "purchase")
    warehouse = await auth_headers(client, "warehouse")
    stock_id = await create_stock(client, warehouse, "重复补库物资")
    first = await create_purchase_plan(
        client, purchase, "重复补库物资", code="DQ-REPEAT", stock_material_id=stock_id
    )
    second = await create_purchase_plan(
        client, purchase, "重复补库物资", code="DQ-REPEAT", stock_material_id=stock_id
    )
    assert first["id"] != second["id"]


@pytest.mark.asyncio
async def test_purchase_tracking_numbers_are_optional_and_order_number_defaults(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client, "purchase")
    blank = await create_purchase_plan(client, headers, "空单号计划", code="DQ-BLANK")
    response = await client.post(
        f"/api/v1/purchase-materials/{blank['id']}/move-to-record",
        headers=headers,
        json={
            "purchase_order_no": "",
            "trace_no": "",
            "purchase_date": "2026-07-18",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["purchase_order_no"] is None
    assert response.json()["trace_no"] is None
    assert response.json()["purchase_date"] == "2026-07-18"

    defaulted = await create_purchase_plan(client, headers, "默认申购单号", code="DQ-DEFAULT")
    response = await client.post(
        f"/api/v1/purchase-materials/{defaulted['id']}/move-to-record",
        headers=headers,
        json={"purchase_date": "2026-07-18"},
    )
    assert response.status_code == 200, response.text
    assert str(response.json()["purchase_order_no"]).startswith("申购 ")
    assert response.json()["trace_no"] is None


@pytest.mark.asyncio
async def test_purchase_excel_exports_use_json_template_specs(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    uncoded = await create_purchase_plan(client, headers, "待编码\u000b接触器")
    coded = await create_purchase_plan(client, headers, "已编码\u000c接触器", code="DQ-XLSX-1")

    code_export = await client.get(
        "/api/v1/purchase-materials/export-uncoded",
        headers=headers,
    )
    assert code_export.status_code == 200, code_export.text
    assert code_export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    code_sheet = load_workbook(BytesIO(code_export.content)).active
    assert code_sheet["D7"].value == "待编码接触器"
    assert code_sheet["E7"].value == uncoded["model_spec"]
    assert code_sheet["I7"].value == uncoded["unit_name"]

    purchase_export = await client.post(
        "/api/v1/purchase-materials/export-purchase-application",
        headers=headers,
        json={"material_ids": [coded["id"]]},
    )
    assert purchase_export.status_code == 200, purchase_export.text
    purchase_sheet = load_workbook(BytesIO(purchase_export.content)).active
    assert purchase_sheet["A1"].value == "物料编码（必填）"
    assert purchase_sheet["A2"].value == coded["material_code"]
    assert purchase_sheet["B2"].value == "已编码接触器"
    assert str(purchase_sheet["C2"].value) == coded["planned_qty"]


@pytest.mark.asyncio
async def test_missing_excel_template_returns_readable_400(
    client: AsyncClient, monkeypatch, tmp_path
) -> None:
    headers = await auth_headers(client, "purchase")
    monkeypatch.setattr(settings, "template_dir", tmp_path)

    response = await client.get("/api/v1/purchase-materials/export-uncoded", headers=headers)

    assert response.status_code == 400
    assert response.json()["code"] == "EXPORT_TEMPLATE_MISSING"
    assert "material-code-application.json" in response.json()["message"]
