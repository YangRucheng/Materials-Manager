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
        "webhook_url": webhook_url,
        "secret": f"{platform.lower()}-secret",
        "webhook_configured": True,
        "secret_configured": True,
        "updated_at": response.json()["updated_at"],
        "version": 1,
    }


@pytest.mark.asyncio
async def test_webhook_settings_permissions_and_validation(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
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
            "webhook_url": "",
            "secret": "",
            "webhook_configured": False,
            "secret_configured": False,
            "updated_at": None,
            "version": 0,
        },
        {
            "platform": "DINGTALK",
            "enabled": False,
            "subscribed_events": [],
            "webhook_url": "",
            "secret": "",
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

    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"code": 0, "msg": "success"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_client:
        monkeypatch.setattr(webhook_service, "_client", mock_client)
        tested = await client.post(
            "/api/v1/system-settings/webhooks/FEISHU/test",
            headers=admin,
            json={
                "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/unsaved-token",
                "secret": "unsaved-secret",
            },
        )
    assert tested.status_code == 200, tested.text
    assert len(captured) == 1
    test_body = __import__("json").loads(captured[0].content)
    assert test_body["content"]["text"] == "测试通知\n这是一条 Webhook 测试通知。"


def test_notification_message_format() -> None:
    single_outbound_payload = {
        "event_type": "stock.outbound.created",
        "data": {
            "operation_no": "OUT-SHOULD-NOT-APPEAR",
            "receiver_name": "张三",
            "subitem_no": "01-02",
            "business_reason": "设备检修",
            "materials": [
                {
                    "name": "接触器",
                    "model_spec": "CJX2",
                    "quantity": "2.0000",
                    "unit_name": "个",
                }
            ],
        },
    }
    title, text = webhook_service._message_text(single_outbound_payload)
    assert title == "出库通知"
    assert text == "物资：接触器 CJX2\n数量：2个\n领用人：张三\n用途：01-02 设备检修"
    assert "流水号" not in text

    multiple_outbound_payload = {
        "event_type": "stock.outbound.created",
        "data": {
            "receiver_name": "张三",
            "subitem_no": "01-02",
            "business_reason": "设备检修",
            "materials": [
                {"name": "接触器", "model_spec": "CJX2"},
                {"name": "断路器", "model_spec": "DZ47"},
                {"name": "继电器", "model_spec": "RXM"},
            ],
        },
    }
    multiple_title, multiple_text = webhook_service._message_text(
        multiple_outbound_payload
    )
    assert multiple_title == "出库通知"
    assert multiple_text == "物资：3项物资\n领用人：张三\n用途：01-02 设备检修"

    inbound_title, inbound_text = webhook_service._message_text(
        {
            "event_type": "stock.inbound.created",
            "data": {"materials": [{"name": "接触器"}, {"name": "断路器"}]},
        }
    )
    assert inbound_title == "入库通知"
    assert inbound_text == "入库数量：2 项"

    user_title, _ = webhook_service._message_text(
        {"event_type": "mini_program.user.bound", "data": {}}
    )
    assert user_title == "新用户绑定通知"


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
    loaded = await client.get("/api/v1/system-settings/webhooks", headers=admin)
    assert loaded.status_code == 200
    loaded_by_platform = {item["platform"]: item for item in loaded.json()}
    assert loaded_by_platform["FEISHU"]["webhook_url"].endswith("/feishu-token")
    assert loaded_by_platform["FEISHU"]["secret"] == "feishu-secret"
    assert loaded_by_platform["DINGTALK"]["webhook_url"].endswith(
        "access_token=dingtalk-token"
    )
    assert loaded_by_platform["DINGTALK"]["secret"] == "dingtalk-secret"

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

    updated = await client.patch(
        f"/api/v1/inventory/operations/{outbound.json()['id']}",
        headers=warehouse,
        json={
            "version": outbound.json()["version"],
            "operation_type": "OUTBOUND",
            "occurred_at": outbound_payload["occurred_at"],
            "source_type": "MANUAL",
            "business_reason": "管理员修改用途",
            "receiver_name": "测试领用人",
            "lines": outbound_payload["lines"],
        },
    )
    assert updated.status_code == 200, updated.text

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
    sent_text = "\n".join(
        __import__("json").loads(item.content)["content"]["text"]
        for item in feishu_requests
    )
    assert "出库通知" in sent_text
    assert "入库通知" in sent_text
    assert "新用户绑定通知" in sent_text
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
