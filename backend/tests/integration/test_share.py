from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.domain.enums import ShareType
from app.models import ShareLink
from app.services import share_link_service
from app.services.common import utcnow
from tests.conftest import auth_headers
from tests.integration.test_procurement import (
    create_purchase_plan,
    move_to_record,
)


async def _create_plan_share(
    client: AsyncClient, headers: dict[str, str], item_ids: list[int], expires_in: str = "24h"
) -> dict:
    response = await client.post(
        "/api/v1/shares",
        headers=headers,
        json={"share_type": "purchase_plan", "item_ids": item_ids, "expires_in": expires_in},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_share_purchase_plan_and_anonymous_view(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "共享计划", code="SHARE-PLAN-001")

    created = await _create_plan_share(client, headers, [int(plan["id"])])
    assert created["share_type"] == "purchase_plan"
    assert created["item_count"] == 1
    assert created["expires_at"] is not None
    token = created["token"]

    # 匿名读取：不带任何认证头。
    view = await client.get(f"/api/v1/shares/{token}")
    assert view.status_code == 200, view.text
    body = view.json()
    assert body["share_type"] == "purchase_plan"
    assert body["item_count"] == 1
    assert body["expires_at"] is not None
    items = body["items"]
    assert len(items) == 1
    item = items[0]
    assert item["id"] == plan["id"]
    assert item["name"] == "共享计划"
    assert item["material_code"] == "SHARE-PLAN-001"
    assert "moved_to_record" in item


@pytest.mark.asyncio
async def test_share_purchase_record_and_anonymous_view(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(
        client, headers, "共享记录", code="SHARE-RECORD-001"
    )
    record = await move_to_record(client, headers, int(plan["id"]))
    line_id = int(record["line_id"])

    response = await client.post(
        "/api/v1/shares",
        headers=headers,
        json={"share_type": "purchase_record", "item_ids": [line_id], "expires_in": "3d"},
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["item_count"] == 1

    view = await client.get(f"/api/v1/shares/{created['token']}")
    assert view.status_code == 200, view.text
    body = view.json()
    assert body["share_type"] == "purchase_record"
    item = body["items"][0]
    assert item["line_id"] == line_id
    assert item["material_name"] == "共享记录"
    assert item["status"] == "已申购"


@pytest.mark.asyncio
async def test_permanent_share_has_no_expiry(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "永久共享")
    created = await _create_plan_share(
        client, headers, [int(plan["id"])], expires_in="permanent"
    )
    assert created["expires_at"] is None

    view = await client.get(f"/api/v1/shares/{created['token']}")
    assert view.status_code == 200, view.text
    assert view.json()["expires_at"] is None


@pytest.mark.asyncio
async def test_expired_share_rejected(client: AsyncClient) -> None:
    async with SessionLocal() as session:
        share = ShareLink(
            share_type=ShareType.PURCHASE_PLAN,
            item_ids=[1],
            expires_at=utcnow() - timedelta(minutes=1),
            created_by=None,
        )
        session.add(share)
        await session.commit()
        await session.refresh(share)
        token = share.token

    view = await client.get(f"/api/v1/shares/{token}")
    assert view.status_code == 400, view.text
    assert view.json()["code"] == "SHARE_EXPIRED"


@pytest.mark.asyncio
async def test_unknown_share_token_rejected(client: AsyncClient) -> None:
    view = await client.get("/api/v1/shares/00000000-0000-7000-8000-000000000000")
    assert view.status_code == 400, view.text
    assert view.json()["code"] == "SHARE_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_share_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/shares",
        json={"share_type": "purchase_plan", "item_ids": [1], "expires_in": "24h"},
    )
    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_create_share_rejects_missing_items(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    response = await client.post(
        "/api/v1/shares",
        headers=headers,
        json={"share_type": "purchase_plan", "item_ids": [999999], "expires_in": "24h"},
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_revoke_share_by_owner_and_super_admin(client: AsyncClient) -> None:
    purchase_headers = await auth_headers(client, "purchase")
    readonly_headers = await auth_headers(client, "readonly")
    admin_headers = await auth_headers(client, "admin")
    plan = await create_purchase_plan(client, purchase_headers, "撤回共享")
    created = await _create_plan_share(client, purchase_headers, [int(plan["id"])])
    token = created["token"]

    # 非创建者也非超管不能撤回。
    forbidden = await client.delete(f"/api/v1/shares/{token}", headers=readonly_headers)
    assert forbidden.status_code == 403, forbidden.text
    view = await client.get(f"/api/v1/shares/{token}")
    assert view.status_code == 200

    # 创建者可撤回，撤回后匿名读取失效。
    revoked = await client.delete(f"/api/v1/shares/{token}", headers=purchase_headers)
    assert revoked.status_code == 204, revoked.text
    view = await client.get(f"/api/v1/shares/{token}")
    assert view.status_code == 400
    assert view.json()["code"] == "SHARE_NOT_FOUND"

    # 超管也可撤回他人创建的分享。
    plan2 = await create_purchase_plan(client, purchase_headers, "超管撤回")
    created2 = await _create_plan_share(client, purchase_headers, [int(plan2["id"])])
    revoked2 = await client.delete(f"/api/v1/shares/{created2['token']}", headers=admin_headers)
    assert revoked2.status_code == 204, revoked2.text


@pytest.mark.asyncio
async def test_cleanup_expired_deletes_only_expired_rows(client: AsyncClient) -> None:
    async with SessionLocal() as session:
        session.add_all(
            [
                ShareLink(
                    share_type=ShareType.PURCHASE_PLAN,
                    item_ids=[1],
                    expires_at=utcnow() - timedelta(hours=1),
                ),
                ShareLink(
                    share_type=ShareType.PURCHASE_PLAN,
                    item_ids=[1],
                    expires_at=utcnow() + timedelta(days=1),
                ),
                ShareLink(
                    share_type=ShareType.PURCHASE_PLAN,
                    item_ids=[1],
                    expires_at=None,
                ),
            ]
        )
        await session.commit()

    purged = await share_link_service.cleanup_expired()
    assert purged == 1

    async with SessionLocal() as session:
        remaining = list((await session.scalars(select(ShareLink))).all())
    assert len(remaining) == 2
