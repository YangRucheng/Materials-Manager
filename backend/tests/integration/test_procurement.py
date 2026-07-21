from __future__ import annotations

from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from PIL import Image

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import PurchaseRequestLine
from tests.conftest import auth_headers, create_stock


async def create_purchase_plan(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    code: str | None = None,
    stock_material_id: int | None = None,
    planned_qty: str = "5",
    model_spec: str = "M60-2P 5A",
    actual_demand_person: str = "车间员工张三",
    purchase_responsible: str = "李工",
    subitem_no: str | None = "01-01",
    plan_date: str = "2026-07-01",
    image_ids: list[str] | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/purchase-materials",
        headers=headers,
        json={
            "plan_date": plan_date,
            "material_code": code,
            "name": name,
            "model_spec": model_spec,
            "unit_id": 1,
            "actual_demand_person": actual_demand_person,
            "purchase_responsible": purchase_responsible,
            "planned_qty": planned_qty,
            "usage": "控制柜检修",
            "subitem_no": subitem_no,
            "remark": "新计划",
            "stock_material_id": stock_material_id,
            "image_ids": image_ids or [],
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["planned_qty"] == planned_qty
    assert result["purchase_responsible"] == purchase_responsible
    assert result["plan_date"] == plan_date
    assert "code_state" not in result
    return result


@pytest.mark.asyncio
async def test_empty_purchase_people_use_backslash_placeholder(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    response = await client.post(
        "/api/v1/purchase-materials",
        headers=headers,
        json={
            "plan_date": "2026-07-21",
            "name": "空负责人测试",
            "model_spec": "TEST-EMPTY",
            "unit_id": 1,
            "planned_qty": "1",
            "usage": "空值占位符测试",
            "image_ids": [],
        },
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["actual_demand_person"] == "\\"
    assert result["purchase_responsible"] == "\\"


@pytest.mark.asyncio
async def test_purchase_lists_support_field_like_and_person_filters(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client, "purchase")
    first = await create_purchase_plan(
        client,
        headers,
        "智能断路器",
        code="DQ-FILTER-001",
        model_spec="DZ47-2P 5A",
        actual_demand_person="张三",
        purchase_responsible="李工",
    )
    second = await create_purchase_plan(
        client,
        headers,
        "交流接触器",
        code="DQ-FILTER-002",
        model_spec="CJX2-18 220V",
        actual_demand_person="李四",
        purchase_responsible="王工",
    )

    plan_search = await client.get(
        "/api/v1/purchase-materials",
        headers=headers,
        params={"search_field": "name", "search_value": "断路", "moved": False},
    )
    assert plan_search.status_code == 200, plan_search.text
    assert [item["id"] for item in plan_search.json()["items"]] == [first["id"]]

    person_search = await client.get(
        "/api/v1/purchase-materials",
        headers=headers,
        params={"purchase_responsible": "王", "moved": False},
    )
    assert person_search.status_code == 200, person_search.text
    assert [item["id"] for item in person_search.json()["items"]] == [second["id"]]

    combined_plan_search = await client.get(
        "/api/v1/purchase-materials",
        headers=headers,
        params={
            "name": "断路",
            "model_spec": "2P",
            "purchase_responsible": "李",
            "moved": False,
        },
    )
    assert combined_plan_search.status_code == 200, combined_plan_search.text
    assert [item["id"] for item in combined_plan_search.json()["items"]] == [first["id"]]

    mismatched_plan_search = await client.get(
        "/api/v1/purchase-materials",
        headers=headers,
        params={"name": "断路", "purchase_responsible": "王", "moved": False},
    )
    assert mismatched_plan_search.status_code == 200, mismatched_plan_search.text
    assert mismatched_plan_search.json()["items"] == []

    plan_options = await client.get(
        "/api/v1/purchase-materials/filter-options",
        headers=headers,
        params={"moved": False},
    )
    assert plan_options.status_code == 200, plan_options.text
    assert set(plan_options.json()["actual_demand_persons"]) == {"张三", "李四"}
    assert set(plan_options.json()["purchase_responsibles"]) == {"李工", "王工"}

    first_record = await move_to_record(
        client, headers, int(first["id"]), trace_no="TRACE-LIKE-001"
    )
    second_record = await move_to_record(
        client, headers, int(second["id"]), trace_no="TRACE-OTHER-002"
    )
    async with SessionLocal() as session:
        line = await session.get(PurchaseRequestLine, int(first_record["line_id"]))
        assert line is not None
        line.status = ""
        await session.commit()

    record_search = await client.get(
        "/api/v1/purchase-records",
        headers=headers,
        params={
            "search_field": "trace_no",
            "search_value": "LIKE-00",
            "actual_demand_person": "张",
            "page_size": 10,
        },
    )
    assert record_search.status_code == 200, record_search.text
    assert record_search.json()["page_size"] == 10
    assert [item["purchase_material_id"] for item in record_search.json()["items"]] == [
        first["id"]
    ]

    combined_record_search = await client.get(
        "/api/v1/purchase-records",
        headers=headers,
        params={
            "name": "接触",
            "model_spec": "220V",
            "purchase_responsible": "王",
        },
    )
    assert combined_record_search.status_code == 200, combined_record_search.text
    assert [
        item["purchase_material_id"] for item in combined_record_search.json()["items"]
    ] == [second["id"]]

    record_options = await client.get(
        "/api/v1/purchase-records/filter-options", headers=headers
    )
    assert record_options.status_code == 200, record_options.text
    assert set(record_options.json()["actual_demand_persons"]) == {"张三", "李四"}
    assert record_options.json()["statuses"] == ["已申购"]

    selected_status = await client.get(
        "/api/v1/purchase-records",
        headers=headers,
        params={"status": "已申购"},
    )
    assert selected_status.status_code == 200, selected_status.text
    assert [item["line_id"] for item in selected_status.json()["items"]] == [
        second_record["line_id"]
    ]

    empty_status = await client.get(
        "/api/v1/purchase-records",
        headers=headers,
        params={"empty_status": True},
    )
    assert empty_status.status_code == 200, empty_status.text
    assert [item["line_id"] for item in empty_status.json()["items"]] == [
        first_record["line_id"]
    ]


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
            "status": "已申购",
            "record_remark": "供应商信息待补充",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_plan_number_uses_date_sequence_and_record_keeps_plan_date(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client, "purchase")
    first = await create_purchase_plan(client, headers, "同日计划一", code="DQ-PLAN-1")
    second = await create_purchase_plan(client, headers, "同日计划二", code="DQ-PLAN-2")
    other_day = await create_purchase_plan(
        client,
        headers,
        "次日计划",
        code="DQ-PLAN-3",
        plan_date="2026-07-02",
    )

    assert first["plan_no"] == "PLAN-20260701-001"
    assert second["plan_no"] == "PLAN-20260701-002"
    assert other_day["plan_no"] == "PLAN-20260702-001"

    record = await move_to_record(client, headers, int(first["id"]))
    assert record["plan_no"] == first["plan_no"]
    assert record["plan_date"] == "2026-07-01"


@pytest.mark.asyncio
async def test_record_keeps_purchase_plan_attachments(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    source = BytesIO()
    Image.new("RGB", (24, 16), "blue").save(source, format="PNG")
    uploaded = await client.post(
        "/api/v1/files/images",
        headers=headers,
        files={"file": ("motor.png", source.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]
    plan = await create_purchase_plan(
        client,
        headers,
        "带附件申购计划",
        code="DQ-IMAGE-001",
        image_ids=[file_id],
    )

    record = await move_to_record(client, headers, int(plan["id"]))

    assert [image["id"] for image in record["images"]] == [file_id]
    detail = await client.get(f"/api/v1/purchase-records/{record['line_id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert [image["id"] for image in detail.json()["images"]] == [file_id]


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
    assert record["purchase_qty"] == "5"
    assert record["status"] == "已申购"


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
            "status": "采购处理中",
            "record_remark": "批量转入",
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
    assert {record["status"] for record in records} == {"采购处理中"}


@pytest.mark.asyncio
async def test_purchase_record_supports_full_edit_and_free_text_status(
    client: AsyncClient,
) -> None:
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
            "plan_date": "2026-07-20",
            "material_code": "DQ-1-REV",
            "material_name": "负责人一修订",
            "model_spec": "M60-2P 10A",
            "unit_id": 1,
            "actual_demand_person": "检修班王五",
            "purchase_responsible": "外部负责人丙",
            "purchase_qty": "8",
            "usage": "统计修订用途",
            "subitem_no": "02-02",
            "plan_remark": "计划备注修订",
            "stock_material_id": None,
            "image_ids": [],
            "purchase_order_no": "SG-A-修订",
            "trace_no": "ZS-A-修订",
            "purchase_date": "2026-07-19",
            "salesperson": "钱经理",
            "status": "供应商已确认，等待财务安排",
            "record_remark": "仅用于整理统计",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["trace_no"] == "ZS-A-修订"
    assert changed.json()["purchase_order_no"] == "SG-A-修订"
    assert changed.json()["purchase_date"] == "2026-07-19"
    assert changed.json()["salesperson"] == "钱经理"
    assert changed.json()["plan_date"] == "2026-07-20"
    assert changed.json()["material_code"] == "DQ-1-REV"
    assert changed.json()["material_name"] == "负责人一修订"
    assert changed.json()["model_spec"] == "M60-2P 10A"
    assert changed.json()["actual_demand_person"] == "检修班王五"
    assert changed.json()["purchase_responsible"] == "外部负责人丙"
    assert changed.json()["purchase_qty"] == "8"
    assert changed.json()["usage"] == "统计修订用途"
    assert changed.json()["subitem_no"] == "02-02"
    assert changed.json()["plan_remark"] == "计划备注修订"
    assert changed.json()["status"] == "供应商已确认，等待财务安排"
    assert changed.json()["record_remark"] == "仅用于整理统计"
    assert "received_qty" not in changed.json()
    assert "remaining_qty" not in changed.json()

    filtered = await client.get(
        "/api/v1/purchase-records",
        headers=headers,
        params={"status": "供应商已确认，等待财务安排"},
    )
    assert filtered.status_code == 200, filtered.text
    assert [item["line_id"] for item in filtered.json()["items"]] == [first_record["line_id"]]

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
async def test_inventory_inbound_does_not_change_purchase_record(client: AsyncClient) -> None:
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

    inbound = await client.post(
        "/api/v1/inventory/inbounds",
        headers=warehouse,
        json={
            "client_request_id": "independent-inbound",
            "occurred_at": "2026-07-17T10:00:00+08:00",
            "source_type": "MANUAL",
            "business_reason": "普通入库，与申购记录无关",
            "lines": [{"stock_material_id": stock_id, "quantity": "5"}],
        },
    )
    assert inbound.status_code == 201, inbound.text
    unchanged = await client.get(
        f"/api/v1/purchase-records/{record['line_id']}", headers=purchase
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["purchase_qty"] == "5"
    assert unchanged.json()["status"] == "已申购"
    assert "received_qty" not in unchanged.json()
    assert "remaining_qty" not in unchanged.json()


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
