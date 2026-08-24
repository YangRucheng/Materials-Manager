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


@pytest.mark.asyncio
async def test_create_share_with_columns_filters_public_view(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "受限共享", code="SHARE-PLAN-COL")
    created = await _create_plan_share(client, headers, [int(plan["id"])])
    token = created["token"]

    # 更新为仅展示部分列。
    updated = await client.patch(
        f"/api/v1/shares/{token}", headers=headers, json={"columns": ["name", "status"]}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["columns"] == ["name", "status"]

    view = await client.get(f"/api/v1/shares/{token}")
    assert view.status_code == 200, view.text
    body = view.json()
    assert body["columns"] == ["name", "status"]
    assert len(body["items"]) == 1
    # 只下发所选列 + 行身份键 id；隐藏列数据（如 usage）不下发。
    assert set(body["items"][0].keys()) == {"id", "name", "status"}
    assert body["items"][0]["name"] == "受限共享"
    assert "usage" not in body["items"][0]
    assert "material_code" not in body["items"][0]


@pytest.mark.asyncio
async def test_share_record_columns_filter_and_identity(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "受限记录", code="SHARE-REC-COL")
    record = await move_to_record(client, headers, int(plan["id"]))
    line_id = int(record["line_id"])

    created = await client.post(
        "/api/v1/shares",
        headers=headers,
        json={
            "share_type": "purchase_record",
            "item_ids": [line_id],
            "expires_in": "7d",
            "columns": ["material_name", "purchase_qty"],
        },
    )
    assert created.status_code == 201, created.text
    token = created.json()["token"]
    assert created.json()["columns"] == ["material_name", "purchase_qty"]

    view = await client.get(f"/api/v1/shares/{token}")
    assert view.status_code == 200, view.text
    item = view.json()["items"][0]
    # 记录行身份键为 line_id。
    assert set(item.keys()) == {"line_id", "material_name", "purchase_qty"}
    assert item["material_name"] == "受限记录"


@pytest.mark.asyncio
async def test_share_without_columns_returns_full_items(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "全列共享", code="SHARE-PLAN-ALL")
    created = await _create_plan_share(client, headers, [int(plan["id"])])
    assert created["columns"] is None

    view = await client.get(f"/api/v1/shares/{created['token']}")
    assert view.status_code == 200, view.text
    body = view.json()
    assert body["columns"] is None
    item = body["items"][0]
    # 未配置列时维持现状：返回完整类型行。
    for key in ("id", "plan_no", "name", "material_code", "usage", "status", "images"):
        assert key in item


@pytest.mark.asyncio
async def test_create_share_rejects_invalid_columns(client: AsyncClient) -> None:
    headers = await auth_headers(client, "purchase")
    plan = await create_purchase_plan(client, headers, "非法列", code="SHARE-PLAN-BAD")

    # 空数组 → 422。
    response = await client.post(
        "/api/v1/shares",
        headers=headers,
        json={
            "share_type": "purchase_plan",
            "item_ids": [int(plan["id"])],
            "expires_in": "24h",
            "columns": [],
        },
    )
    assert response.status_code == 422, response.text

    # 重复列 → 422。
    response = await client.post(
        "/api/v1/shares",
        headers=headers,
        json={
            "share_type": "purchase_plan",
            "item_ids": [int(plan["id"])],
            "expires_in": "24h",
            "columns": ["name", "name"],
        },
    )
    assert response.status_code == 422, response.text

    # 类型错配（申购计划用申购记录列）→ 422（服务层校验）。
    response = await client.post(
        "/api/v1/shares",
        headers=headers,
        json={
            "share_type": "purchase_plan",
            "item_ids": [int(plan["id"])],
            "expires_in": "24h",
            "columns": ["salesperson"],
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_update_share_columns_permission_and_reset(client: AsyncClient) -> None:
    purchase_headers = await auth_headers(client, "purchase")
    readonly_headers = await auth_headers(client, "readonly")
    plan = await create_purchase_plan(client, purchase_headers, "改列共享")
    created = await _create_plan_share(client, purchase_headers, [int(plan["id"])])
    token = created["token"]

    # 非创建者也非超管不能改列。
    forbidden = await client.patch(
        f"/api/v1/shares/{token}", headers=readonly_headers, json={"columns": ["name"]}
    )
    assert forbidden.status_code == 403, forbidden.text
    assert forbidden.json()["code"] == "FORBIDDEN"

    # 未知 token → 400 NOT_FOUND。
    unknown = await client.patch(
        "/api/v1/shares/00000000-0000-7000-8000-000000000000",
        headers=purchase_headers,
        json={"columns": ["name"]},
    )
    assert unknown.status_code == 400, unknown.text
    assert unknown.json()["code"] == "NOT_FOUND"

    # 创建者可改列；null 恢复展示全部列。
    updated = await client.patch(
        f"/api/v1/shares/{token}", headers=purchase_headers, json={"columns": ["name"]}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["columns"] == ["name"]

    reset = await client.patch(
        f"/api/v1/shares/{token}", headers=purchase_headers, json={"columns": None}
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["columns"] is None

    view = await client.get(f"/api/v1/shares/{token}")
    assert view.status_code == 200, view.text
    assert view.json()["columns"] is None
    assert "usage" in view.json()["items"][0]


@pytest.mark.asyncio
async def test_list_shares_scoped_to_owner_and_super_admin(client: AsyncClient) -> None:
    purchase_headers = await auth_headers(client, "purchase")
    admin_headers = await auth_headers(client, "admin")
    readonly_headers = await auth_headers(client, "readonly")

    # 未认证 → 401。
    unauthorized = await client.get("/api/v1/shares")
    assert unauthorized.status_code == 401, unauthorized.text

    # 申购管理员创建两条分享。
    plan = await create_purchase_plan(client, purchase_headers, "列表共享一")
    await _create_plan_share(client, purchase_headers, [int(plan["id"])])
    plan2 = await create_purchase_plan(client, purchase_headers, "列表共享二")
    await _create_plan_share(client, purchase_headers, [int(plan2["id"])])

    # 创建者只看自己的两条。
    own = await client.get("/api/v1/shares", headers=purchase_headers, params={"page_size": 20})
    assert own.status_code == 200, own.text
    body = own.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert len(body["items"]) == 2
    for item in body["items"]:
        assert item["created_by_name"] == "申购管理员"
        assert set(item.keys()) >= {
            "token",
            "share_type",
            "item_count",
            "expires_at",
            "created_at",
            "created_by",
            "created_by_name",
            "columns",
        }
        assert item["columns"] is None

    # 只读用户没有自己创建的分享。
    none_own = await client.get("/api/v1/shares", headers=readonly_headers)
    assert none_own.status_code == 200, none_own.text
    assert none_own.json()["total"] == 0

    # 超管看全部（含申购管理员创建的）。
    all_shares = await client.get("/api/v1/shares", headers=admin_headers)
    assert all_shares.status_code == 200, all_shares.text
    assert all_shares.json()["total"] == 2

    # 分页：page_size=1 时应有两页。
    paged = await client.get(
        "/api/v1/shares", headers=purchase_headers, params={"page": 1, "page_size": 1}
    )
    assert paged.status_code == 200, paged.text
    assert paged.json()["total"] == 2
    assert len(paged.json()["items"]) == 1
