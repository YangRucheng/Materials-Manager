"""申购记录同步专用接口测试：/purchase-record-sync/*。

覆盖：目标列表与游标分页、按追溯号回写（空才填/状态只进不退/version 自增）、
权限校验、NOT_FOUND。
"""

import pytest

from tests.conftest import auth_headers
from tests.integration.test_procurement import create_purchase_plan

pytestmark = pytest.mark.asyncio


async def _move_plan(client, headers, plan_id, trace_no):
    response = await client.post(
        f"/api/v1/purchase-materials/{plan_id}/move-to-record",
        headers=headers,
        json={
            "purchase_order_no": "SYNC-PO",
            "trace_no": trace_no,
            "contract_no": None,
            "vessel_no": None,
            "consolidation_date": None,
            "consolidation_port": None,
            "sailing_date": None,
            "purchase_date": "2026-07-18",
            "salesperson": None,
            "status": "已申购",
            "record_remark": "同步测试",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _apply_trace(client, headers, trace_no, payload):
    response = await client.post(
        f"/api/v1/purchase-record-sync/trace/{trace_no}", headers=headers, json=payload
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _targets(client, headers, **params):
    response = await client.get(
        "/api/v1/purchase-record-sync/targets", headers=headers, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _record(client, headers, line_id):
    response = await client.get(f"/api/v1/purchase-records/{line_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_sync_targets_apply_and_version(client) -> None:
    headers = await auth_headers(client, "purchase")
    motor = await create_purchase_plan(client, headers, "同步电机A", code="SYNC-A")
    record = await _move_plan(client, headers, int(motor["id"]), "SYNC-001")

    targets = await _targets(client, headers)
    assert [item["trace_no"] for item in targets["items"]] == ["SYNC-001"]

    result = await _apply_trace(
        client,
        headers,
        "SYNC-001",
        {
            "salesperson": "赵经理",
            "contract_no": "HT-SYNC-1",
            "vessel_no": "VESSEL-SYNC-1",
            "status": "已采购",
        },
    )
    assert result == {"affected_headers": 1, "affected_lines": 1}

    rec = await _record(client, headers, record["line_id"])
    assert rec["contract_no"] == "HT-SYNC-1"
    assert rec["vessel_no"] == "VESSEL-SYNC-1"
    assert rec["salesperson"] == "赵经理"
    assert rec["status"] == "已采购"
    assert rec["version"] == 2


async def test_sync_only_fills_empty_and_advances_status(client) -> None:
    headers = await auth_headers(client, "purchase")
    motor = await create_purchase_plan(client, headers, "同步电机B", code="SYNC-B")
    record = await _move_plan(client, headers, int(motor["id"]), "SYNC-002")

    await _apply_trace(
        client,
        headers,
        "SYNC-002",
        {
            "salesperson": "赵经理",
            "contract_no": "HT-SYNC-2",
            "vessel_no": "VESSEL-2",
            "status": "已采购",
        },
    )

    # 已填字段不被覆盖、状态不回退
    result = await _apply_trace(
        client, headers, "SYNC-002", {"salesperson": "新业务员", "status": "已申购"}
    )
    assert result == {"affected_headers": 0, "affected_lines": 0}
    rec = await _record(client, headers, record["line_id"])
    assert rec["salesperson"] == "赵经理"
    assert rec["status"] == "已采购"

    # 前进到已入库后，若按新脚本关心的字段（不含集港/发运）筛选，该追溯号不再是目标
    result = await _apply_trace(client, headers, "SYNC-002", {"status": "已入库"})
    assert result == {"affected_headers": 0, "affected_lines": 1}
    targets = await _targets(
        client, headers, fields="contract_no,vessel_no,salesperson,status"
    )
    assert all(item["trace_no"] != "SYNC-002" for item in targets["items"])
    # 但按全部字段（含集港/发运）筛选时，因集港/发运仍为空，仍视为目标
    targets_all = await _targets(client, headers)
    assert any(item["trace_no"] == "SYNC-002" for item in targets_all["items"])


async def test_sync_targets_invalid_fields(client) -> None:
    headers = await auth_headers(client, "purchase")
    response = await client.get(
        "/api/v1/purchase-record-sync/targets", headers=headers, params={"fields": "nope"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_sync_targets_cursor_pagination(client) -> None:
    headers = await auth_headers(client, "purchase")
    for index in range(1, 4):
        motor = await create_purchase_plan(
            client, headers, f"同步电机E{index}", code=f"SYNC-E{index}"
        )
        await _move_plan(client, headers, int(motor["id"]), f"SYNC-E{index}")

    first = await _targets(client, headers, limit=2)
    assert len(first["items"]) == 2
    assert first["has_more"] is True
    next_cursor = first["next_cursor"]
    assert next_cursor > 0

    second = await _targets(client, headers, limit=2, cursor=next_cursor)
    assert len(second["items"]) == 1
    assert second["has_more"] is False
    trace_nos = {item["trace_no"] for item in first["items"]} | {
        item["trace_no"] for item in second["items"]
    }
    assert trace_nos == {"SYNC-E1", "SYNC-E2", "SYNC-E3"}


async def test_sync_requires_purchase_writer(client) -> None:
    readonly = await auth_headers(client, "readonly")
    response = await client.get("/api/v1/purchase-record-sync/targets", headers=readonly)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"

    response = await client.post(
        "/api/v1/purchase-record-sync/trace/ANY", headers=readonly, json={}
    )
    assert response.status_code == 403


async def test_sync_trace_not_found(client) -> None:
    headers = await auth_headers(client, "purchase")
    response = await client.post(
        "/api/v1/purchase-record-sync/trace/NO-SUCH", headers=headers, json={}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "NOT_FOUND"
