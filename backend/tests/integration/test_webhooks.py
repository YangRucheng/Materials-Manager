from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.security import create_mini_program_registration_token
from app.domain.enums import WebhookDeliveryStatus, WebhookPlatform
from app.models import WebhookChannel, WebhookDelivery
from app.services import webhook_service
from tests.conftest import auth_headers, create_stock


async def configure_channel(
    client: AsyncClient,
    headers: dict[str, str],
    platform: str,
    webhook_url: str,
    events: list[str],
) -> None:
    response = await client.put(
        f"/api/v1/system-settings/webhooks/{platform}",
        headers=headers,
        json={
            "enabled": True,
            "webhook_url": webhook_url,
            "secret": f"{platform.lower()}-secret",
            "subscribed_events": events,
            "version": 0,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "platform": platform,
        "enabled": True,
        "subscribed_events": events,
        "webhook_configured": True,
        "secret_configured": True,
        "updated_at": response.json()["updated_at"],
        "version": 1,
    }


@pytest.mark.asyncio
async def test_webhook_settings_permissions_and_validation(client: AsyncClient) -> None:
    unauthorized = await client.get("/api/v1/system-settings/webhooks")
    assert unauthorized.status_code == 401

    readonly = await auth_headers(client, "readonly")
    forbidden = await client.get("/api/v1/system-settings/webhooks", headers=readonly)
    assert forbidden.status_code == 403

    admin = await auth_headers(client, "admin")
    channels = await client.get("/api/v1/system-settings/webhooks", headers=admin)
    assert channels.status_code == 200
    assert channels.json() == [
        {
            "platform": "FEISHU",
            "enabled": False,
            "subscribed_events": [],
            "webhook_configured": False,
            "secret_configured": False,
            "updated_at": None,
            "version": 0,
        },
        {
            "platform": "DINGTALK",
            "enabled": False,
            "subscribed_events": [],
            "webhook_configured": False,
            "secret_configured": False,
            "updated_at": None,
            "version": 0,
        },
    ]

    invalid = await client.put(
        "/api/v1/system-settings/webhooks/FEISHU",
        headers=admin,
        json={
            "enabled": True,
            "webhook_url": "https://example.com/hook/token",
            "secret": "",
            "subscribed_events": ["stock.outbound.created"],
            "version": 0,
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "INVALID_WEBHOOK_URL"


@pytest.mark.asyncio
async def test_selected_events_are_enqueued_once_and_delivered_to_both_platforms(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await auth_headers(client, "admin")
    warehouse = await auth_headers(client, "warehouse")
    await configure_channel(
        client,
        admin,
        "FEISHU",
        "https://open.feishu.cn/open-apis/bot/v2/hook/feishu-token",
        [
            "stock.outbound.created",
            "stock.inbound.created",
            "mini_program.user.bound",
        ],
    )
    await configure_channel(
        client,
        admin,
        "DINGTALK",
        "https://oapi.dingtalk.com/robot/send?access_token=dingtalk-token",
        ["stock.outbound.created", "mini_program.user.bound"],
    )

    async with SessionLocal() as session:
        stored = list((await session.scalars(select(WebhookChannel))).all())
        assert len(stored) == 2
        assert all("https://" not in item.webhook_url_encrypted for item in stored)
        assert all("-secret" not in item.secret_encrypted for item in stored)

    material_id = await create_stock(client, warehouse, "Webhook 测试物资")
    inbound_payload = {
        "client_request_id": "webhook-inbound",
        "occurred_at": "2026-07-31T08:00:00+08:00",
        "source_type": "MANUAL",
        "business_reason": "Webhook 入库测试",
        "lines": [{"stock_material_id": material_id, "quantity": "10"}],
    }
    inbound = await client.post(
        "/api/v1/inventory/inbounds", headers=warehouse, json=inbound_payload
    )
    assert inbound.status_code == 201, inbound.text

    outbound_payload = {
        "client_request_id": "webhook-outbound",
        "occurred_at": "2026-07-31T09:00:00+08:00",
        "source_type": "MANUAL",
        "business_reason": "Webhook 出库测试",
        "receiver_name": "测试领用人",
        "lines": [{"stock_material_id": material_id, "quantity": "2"}],
    }
    outbound = await client.post(
        "/api/v1/inventory/outbounds", headers=warehouse, json=outbound_payload
    )
    replayed = await client.post(
        "/api/v1/inventory/outbounds", headers=warehouse, json=outbound_payload
    )
    assert outbound.status_code == replayed.status_code == 201
    assert outbound.json()["id"] == replayed.json()["id"]

    registration_token = create_mini_program_registration_token(
        "wx-test-primary", "webhook-new-user-openid"
    )
    profile = await client.post(
        "/api/v1/mini-program/profile",
        headers={"Authorization": f"Bearer {registration_token}"},
        json={"display_name": "Webhook 用户", "department_name": "电气车间"},
    )
    replayed_profile = await client.post(
        "/api/v1/mini-program/profile",
        headers={"Authorization": f"Bearer {registration_token}"},
        json={"display_name": "重复用户", "department_name": "重复部门"},
    )
    assert profile.status_code == replayed_profile.status_code == 200
    assert profile.json()["user"]["id"] == replayed_profile.json()["user"]["id"]

    async with SessionLocal() as session:
        deliveries = list(
            (await session.scalars(select(WebhookDelivery).order_by(WebhookDelivery.id))).all()
        )
        assert len(deliveries) == 5
        assert [item.event_type.value for item in deliveries].count(
            "stock.inbound.created"
        ) == 1
        assert [item.event_type.value for item in deliveries].count(
            "stock.outbound.created"
        ) == 2
        assert [item.event_type.value for item in deliveries].count(
            "mini_program.user.bound"
        ) == 2

    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.host == "open.feishu.cn":
            return httpx.Response(200, json={"code": 0, "msg": "success"})
        return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_client:
        monkeypatch.setattr(webhook_service, "_client", mock_client)
        while await webhook_service.deliver_pending_once():
            pass

    assert len(captured) == 5
    feishu_requests = [item for item in captured if item.url.host == "open.feishu.cn"]
    dingtalk_requests = [item for item in captured if item.url.host == "oapi.dingtalk.com"]
    assert len(feishu_requests) == 3
    assert len(dingtalk_requests) == 2
    feishu_body = __import__("json").loads(feishu_requests[0].content)
    assert feishu_body["msg_type"] == "text"
    assert feishu_body["timestamp"]
    assert feishu_body["sign"]
    dingtalk_query = parse_qs(urlparse(str(dingtalk_requests[0].url)).query)
    assert dingtalk_query["timestamp"]
    assert dingtalk_query["sign"]

    async with SessionLocal() as session:
        succeeded = await session.scalar(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.status == WebhookDeliveryStatus.SUCCEEDED)
        )
        assert succeeded == 5
        platforms = set(
            (
                await session.scalars(
                    select(WebhookChannel.platform).where(WebhookChannel.enabled.is_(True))
                )
            ).all()
        )
        assert platforms == {WebhookPlatform.FEISHU, WebhookPlatform.DINGTALK}
