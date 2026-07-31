from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import AppError, version_conflict
from app.domain.enums import (
    WebhookDeliveryStatus,
    WebhookEventType,
    WebhookPlatform,
)
from app.models import WebhookChannel, WebhookDelivery
from app.schemas import WebhookChannelRead, WebhookChannelUpdate, WebhookTestRequest
from app.services.common import utc_aware, utcnow

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 5
_RETRY_MINUTES = (1, 5, 15, 60, 180)
_POLL_INTERVAL_SECONDS = 2.0
_SENDING_LEASE_MINUTES = 5
_client = httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0))


@dataclass(frozen=True)
class ClaimedDelivery:
    delivery_id: int
    platform: WebhookPlatform
    webhook_url: str
    secret: str
    payload: dict[str, Any]
    attempts: int


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError(
            "WEBHOOK_CREDENTIAL_DECRYPT_FAILED",
            "Webhook 配置无法解密，请由超级管理员重新保存",
            status_code=503,
        ) from exc


def _validate_webhook_url(platform: WebhookPlatform, value: str) -> str:
    url = value.strip()
    if not url:
        return ""
    parsed = urlparse(url)
    allowed_hosts = {
        WebhookPlatform.FEISHU: {"open.feishu.cn", "open.larksuite.com"},
        WebhookPlatform.DINGTALK: {"oapi.dingtalk.com"},
    }
    expected_path = {
        WebhookPlatform.FEISHU: "/open-apis/bot/v2/hook/",
        WebhookPlatform.DINGTALK: "/robot/send",
    }
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts[platform]
        or expected_path[platform] not in parsed.path
    ):
        platform_name = "飞书" if platform == WebhookPlatform.FEISHU else "钉钉"
        raise AppError(
            "INVALID_WEBHOOK_URL",
            f"请输入有效的{platform_name}机器人 Webhook 地址",
            status_code=422,
        )
    return url


def channel_read(channel: WebhookChannel | None, platform: WebhookPlatform) -> WebhookChannelRead:
    if channel is None:
        return WebhookChannelRead(
            platform=platform,
            enabled=False,
            subscribed_events=[],
            webhook_url="",
            secret="",
            webhook_configured=False,
            secret_configured=False,
            updated_at=None,
            version=0,
        )
    return WebhookChannelRead(
        platform=channel.platform,
        enabled=channel.enabled,
        subscribed_events=[WebhookEventType(value) for value in channel.subscribed_events],
        webhook_url=_decrypt(channel.webhook_url_encrypted),
        secret=_decrypt(channel.secret_encrypted),
        webhook_configured=bool(channel.webhook_url_encrypted),
        secret_configured=bool(channel.secret_encrypted),
        updated_at=utc_aware(channel.updated_at),
        version=channel.version,
    )


async def list_channels(session: AsyncSession) -> list[WebhookChannelRead]:
    stored = {item.platform: item for item in (await session.scalars(select(WebhookChannel))).all()}
    return [channel_read(stored.get(platform), platform) for platform in WebhookPlatform]


async def update_channel(
    session: AsyncSession,
    platform: WebhookPlatform,
    data: WebhookChannelUpdate,
) -> WebhookChannel:
    channel = await session.scalar(
        select(WebhookChannel).where(WebhookChannel.platform == platform).with_for_update()
    )
    actual_version = channel.version if channel else 0
    if data.version != actual_version:
        raise version_conflict(data.version, actual_version)

    webhook_url = _validate_webhook_url(platform, data.webhook_url)
    if data.enabled and not webhook_url:
        raise AppError(
            "WEBHOOK_URL_REQUIRED",
            "启用推送前请填写 Webhook 地址",
            status_code=422,
        )
    if data.enabled and not data.subscribed_events:
        raise AppError(
            "WEBHOOK_EVENTS_REQUIRED",
            "启用推送前请至少选择一个事件",
            status_code=422,
        )

    if channel is None:
        channel = WebhookChannel(platform=platform)
        session.add(channel)
    channel.enabled = data.enabled
    channel.subscribed_events = [event.value for event in data.subscribed_events]
    channel.webhook_url_encrypted = _encrypt(webhook_url) if webhook_url else ""
    channel.secret_encrypted = _encrypt(data.secret) if data.secret else ""
    channel.version = actual_version + 1
    await session.flush()
    return channel


async def enqueue_event(
    session: AsyncSession,
    event_type: WebhookEventType,
    data: dict[str, Any],
) -> None:
    channels = list(
        (
            await session.scalars(select(WebhookChannel).where(WebhookChannel.enabled.is_(True)))
        ).all()
    )
    event_id = str(uuid4())
    occurred_at = utcnow().isoformat(timespec="seconds") + "Z"
    for channel in channels:
        if event_type.value not in channel.subscribed_events:
            continue
        session.add(
            WebhookDelivery(
                event_id=event_id,
                event_type=event_type,
                channel_id=channel.id,
                payload={
                    "event_id": event_id,
                    "event_type": event_type.value,
                    "occurred_at": occurred_at,
                    "data": data,
                },
            )
        )
    await session.flush()


def _event_title(event_type: str) -> str:
    return {
        WebhookEventType.STOCK_OUTBOUND_CREATED.value: "出库通知",
        WebhookEventType.STOCK_INBOUND_CREATED.value: "入库通知",
        WebhookEventType.MINI_PROGRAM_USER_BOUND.value: "新用户绑定通知",
        "webhook.test": "测试通知",
    }.get(event_type, "通知")


def _message_text(payload: dict[str, Any]) -> tuple[str, str]:
    event_type = str(payload.get("event_type", ""))
    title = _event_title(event_type)
    raw_data = payload.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    if event_type == "webhook.test":
        details = ["这是一条 Webhook 测试通知。"]
    elif event_type == WebhookEventType.STOCK_OUTBOUND_CREATED.value:
        raw_materials = data.get("materials")
        materials: list[Any] = raw_materials if isinstance(raw_materials, list) else []
        details = []
        for index, item in enumerate(materials[:2], start=1):
            if not isinstance(item, dict):
                continue
            details.append(
                f"物资{index}：{item.get('name', '-')} / {item.get('model_spec', '-')}"
            )
        details.extend(
            [
                f"领用人：{data.get('receiver_name') or '-'}",
                f"用途：{data.get('business_reason') or '-'}",
            ]
        )
        if len(materials) > 1:
            details.append(f"出库总数：{len(materials)} 项")
    elif event_type == WebhookEventType.STOCK_INBOUND_CREATED.value:
        raw_materials = data.get("materials")
        materials = raw_materials if isinstance(raw_materials, list) else []
        details = [f"入库数量：{len(materials)} 项"]
    else:
        details = [
            f"姓名：{data.get('display_name', '-')}",
            f"部门：{data.get('department_name', '-')}",
            f"账号状态：{'已启用' if data.get('enabled') else '待审核'}",
            f"绑定时间：{data.get('bound_at', '-')}",
        ]
    return title, "\n".join(details)


def _feishu_body(payload: dict[str, Any], secret: str) -> dict[str, Any]:
    title, text = _message_text(payload)
    body: dict[str, Any] = {
        "msg_type": "text",
        "content": {"text": f"{title}\n{text}"},
    }
    if secret:
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{secret}".encode()
        body["timestamp"] = timestamp
        body["sign"] = base64.b64encode(
            hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
        ).decode()
    return body


def _dingtalk_request(
    webhook_url: str, payload: dict[str, Any], secret: str
) -> tuple[str, dict[str, Any]]:
    title, text = _message_text(payload)
    if secret:
        timestamp = str(int(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}".encode()
        sign = base64.b64encode(
            hmac.new(secret.encode(), string_to_sign, hashlib.sha256).digest()
        ).decode()
        parsed = urlparse(webhook_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.update({"timestamp": timestamp, "sign": sign})
        webhook_url = urlunparse(parsed._replace(query=urlencode(query)))
    markdown_text = text.replace("\n", "\n\n")
    return webhook_url, {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"### {title}\n\n{markdown_text}",
        },
    }


async def _send(
    platform: WebhookPlatform,
    webhook_url: str,
    secret: str,
    payload: dict[str, Any],
) -> tuple[int, str]:
    if platform == WebhookPlatform.FEISHU:
        response = await _client.post(webhook_url, json=_feishu_body(payload, secret))
    else:
        target_url, body = _dingtalk_request(webhook_url, payload, secret)
        response = await _client.post(target_url, json=body)
    excerpt = response.text[:1000]
    response.raise_for_status()
    try:
        result = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Webhook 返回了无效的 JSON") from exc
    code = (
        result.get("code", result.get("StatusCode", 0))
        if platform == WebhookPlatform.FEISHU
        else result.get("errcode", 0)
    )
    if code != 0:
        message = result.get("msg", result.get("StatusMessage", result.get("errmsg", "未知错误")))
        raise RuntimeError(f"Webhook 平台拒绝请求：{message}")
    return response.status_code, excerpt


def _test_payload() -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": "webhook.test",
        "occurred_at": utcnow().isoformat(timespec="seconds") + "Z",
        "data": {},
    }


async def test_channel(platform: WebhookPlatform, data: WebhookTestRequest) -> None:
    webhook_url = _validate_webhook_url(platform, data.webhook_url)
    if not webhook_url:
        raise AppError("WEBHOOK_URL_REQUIRED", "请填写 Webhook 地址", status_code=422)
    try:
        await _send(
            platform,
            webhook_url,
            data.secret,
            _test_payload(),
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        raise AppError(
            "WEBHOOK_TEST_FAILED",
            f"测试推送失败：{exc}",
            status_code=502,
        ) from exc


async def _claim_delivery() -> ClaimedDelivery | None:
    now = utcnow()
    stale_at = now - timedelta(minutes=_SENDING_LEASE_MINUTES)
    async with SessionLocal() as session:
        delivery = await session.scalar(
            select(WebhookDelivery)
            .where(
                or_(
                    (WebhookDelivery.status == WebhookDeliveryStatus.PENDING)
                    & (WebhookDelivery.next_retry_at <= now),
                    (WebhookDelivery.status == WebhookDeliveryStatus.SENDING)
                    & (WebhookDelivery.updated_at <= stale_at),
                )
            )
            .order_by(WebhookDelivery.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if delivery is None:
            return None
        delivery.status = WebhookDeliveryStatus.SENDING
        delivery.attempts += 1
        delivery.updated_at = now
        claimed = ClaimedDelivery(
            delivery_id=delivery.id,
            platform=delivery.channel.platform,
            webhook_url=_decrypt(delivery.channel.webhook_url_encrypted),
            secret=_decrypt(delivery.channel.secret_encrypted),
            payload=delivery.payload,
            attempts=delivery.attempts,
        )
        await session.commit()
        return claimed


async def _finish_delivery(
    claimed: ClaimedDelivery,
    *,
    response_status: int | None = None,
    response_excerpt: str | None = None,
    error: Exception | None = None,
) -> None:
    async with SessionLocal() as session:
        delivery = await session.get(WebhookDelivery, claimed.delivery_id)
        if delivery is None:
            return
        delivery.updated_at = utcnow()
        delivery.response_status = response_status
        delivery.response_excerpt = response_excerpt
        if error is None:
            delivery.status = WebhookDeliveryStatus.SUCCEEDED
            delivery.delivered_at = utcnow()
            delivery.last_error = None
        else:
            delivery.last_error = str(error)[:1000]
            if claimed.attempts >= _MAX_ATTEMPTS:
                delivery.status = WebhookDeliveryStatus.FAILED
            else:
                delivery.status = WebhookDeliveryStatus.PENDING
                delivery.next_retry_at = utcnow() + timedelta(
                    minutes=_RETRY_MINUTES[claimed.attempts - 1]
                )
        await session.commit()


async def deliver_pending_once() -> bool:
    claimed = await _claim_delivery()
    if claimed is None:
        return False
    try:
        status, excerpt = await _send(
            claimed.platform,
            claimed.webhook_url,
            claimed.secret,
            claimed.payload,
        )
    except Exception as exc:
        logger.warning(
            "webhook delivery failed delivery_id=%s platform=%s attempts=%s error_type=%s",
            claimed.delivery_id,
            claimed.platform,
            claimed.attempts,
            type(exc).__name__,
        )
        await _finish_delivery(claimed, error=exc)
    else:
        await _finish_delivery(claimed, response_status=status, response_excerpt=excerpt)
    return True


async def run_delivery_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            delivered = await deliver_pending_once()
        except Exception:
            logger.exception("webhook delivery worker iteration failed")
            delivered = False
        if delivered:
            continue
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_POLL_INTERVAL_SECONDS)
        except TimeoutError:
            pass


async def close_client() -> None:
    await _client.aclose()
