from fastapi import APIRouter

from app.core.permissions import DbSession, SuperAdmin
from app.domain.enums import WebhookPlatform
from app.schemas import (
    ImageAccelerationSettingsRead,
    WebhookChannelRead,
    WebhookChannelUpdate,
    WebhookTestRead,
    WebhookTestRequest,
)
from app.services import ai_search_service, webhook_service

router = APIRouter(prefix="/system-settings", tags=["系统设置"])


@router.get("/image-acceleration", response_model=ImageAccelerationSettingsRead)
async def image_acceleration_settings(session: DbSession) -> ImageAccelerationSettingsRead:
    server_url = await ai_search_service.get_image_acceleration_server_url(session)
    return ImageAccelerationSettingsRead(image_acceleration_server_url=server_url)


@router.get("/webhooks", response_model=list[WebhookChannelRead])
async def webhook_channels(session: DbSession, user: SuperAdmin) -> list[WebhookChannelRead]:
    return await webhook_service.list_channels(session)


@router.put("/webhooks/{platform}", response_model=WebhookChannelRead)
async def update_webhook_channel(
    platform: WebhookPlatform,
    data: WebhookChannelUpdate,
    session: DbSession,
    user: SuperAdmin,
) -> WebhookChannelRead:
    channel = await webhook_service.update_channel(session, platform, data)
    return webhook_service.channel_read(channel, platform)


@router.post("/webhooks/{platform}/test", response_model=WebhookTestRead)
async def test_webhook_channel(
    platform: WebhookPlatform,
    data: WebhookTestRequest,
    user: SuperAdmin,
) -> WebhookTestRead:
    await webhook_service.test_channel(platform, data)
    return WebhookTestRead(platform=platform, success=True, message="测试消息已发送")
