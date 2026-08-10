from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.constants import SHANGHAI
from app.core.database import SessionLocal
from app.models import PurchaseMaterial, PurchaseRequestLine
from app.services import purchase_plan_cleanup_service
from tests.conftest import auth_headers
from tests.integration.test_procurement import create_purchase_plan, move_to_record


@pytest.mark.asyncio
async def test_cleanup_removes_moved_plans_and_keeps_record(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "待清理计划", code="DQ-CLEAN-1")
    record = await move_to_record(client, headers, int(plan["id"]))

    deleted = await purchase_plan_cleanup_service.cleanup_moved_plans_once()
    assert deleted == 1

    async with SessionLocal() as session:
        assert await session.get(PurchaseMaterial, int(plan["id"])) is None
        line = await session.get(PurchaseRequestLine, int(record["line_id"]))
        assert line is not None
        assert line.purchase_material_id is None
        assert line.plan_no_snapshot == plan["plan_no"]

    after = await client.get(
        f"/api/v1/purchase-records/{record['line_id']}", headers=headers
    )
    assert after.status_code == 200, after.text
    assert after.json()["material_name"] == plan["name"]
    assert after.json()["plan_no"] == plan["plan_no"]


@pytest.mark.asyncio
async def test_cleanup_is_idempotent(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "幂等计划", code="DQ-IDEMP-1")
    await move_to_record(client, headers, int(plan["id"]))

    assert await purchase_plan_cleanup_service.cleanup_moved_plans_once() == 1
    assert await purchase_plan_cleanup_service.cleanup_moved_plans_once() == 0


@pytest.mark.asyncio
async def test_cleanup_skips_unmigrated_snapshot(client: AsyncClient) -> None:
    """迁移护栏：plan_no_snapshot 为 NULL（未回填）的计划不被清理。"""
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "未迁移计划", code="DQ-NOMIG-1")
    record = await move_to_record(client, headers, int(plan["id"]))

    async with SessionLocal() as session:
        line = await session.get(PurchaseRequestLine, int(record["line_id"]))
        assert line is not None
        line.plan_no_snapshot = ""  # 模拟旧库未回填（NULL 或空值）
        await session.commit()

    assert await purchase_plan_cleanup_service.cleanup_moved_plans_once() == 0
    async with SessionLocal() as session:
        assert await session.get(PurchaseMaterial, int(plan["id"])) is not None


@pytest.mark.asyncio
async def test_cleanup_batches_over_limit(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan_ids: list[int] = []
    for index in range(purchase_plan_cleanup_service._BATCH_SIZE + 5):
        plan = await create_purchase_plan(
            client, headers, f"批量清理{index}", code=f"DQ-BATCH-{index:02d}"
        )
        plan_ids.append(int(plan["id"]))
        await move_to_record(client, headers, int(plan["id"]))

    total_deleted = 0
    while (deleted := await purchase_plan_cleanup_service.cleanup_moved_plans_once()) > 0:
        total_deleted += deleted
        assert deleted <= purchase_plan_cleanup_service._BATCH_SIZE
    assert total_deleted == len(plan_ids)


def test_seconds_until_two_am() -> None:
    shanghai = timezone(timedelta(hours=8))
    before = datetime(2026, 8, 10, 1, 30, 0, tzinfo=shanghai)
    assert purchase_plan_cleanup_service._seconds_until_two_am(before) == 1800.0
    at_two = datetime(2026, 8, 10, 2, 0, 0, tzinfo=shanghai)
    assert purchase_plan_cleanup_service._seconds_until_two_am(at_two) == 86400.0
    after = datetime(2026, 8, 10, 14, 0, 0, tzinfo=shanghai)
    assert purchase_plan_cleanup_service._seconds_until_two_am(after) == 43200.0


def test_shanghai_constant() -> None:
    assert SHANGHAI == timezone(timedelta(hours=8))
