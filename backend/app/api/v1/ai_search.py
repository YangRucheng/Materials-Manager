from fastapi import APIRouter

from app.core.permissions import CurrentUser, DbSession, SuperAdmin
from app.schemas import (
    AiSearchExpandRead,
    AiSearchExpandRequest,
    AiSearchSettingsRead,
    AiSearchSettingsUpdate,
    AiSearchStatusRead,
    AiSearchTestRead,
)
from app.services import ai_search_service

router = APIRouter(prefix="/ai-search", tags=["AI 搜索"])


@router.post("/expand", response_model=AiSearchExpandRead)
async def expand(
    data: AiSearchExpandRequest, session: DbSession, user: CurrentUser
) -> AiSearchExpandRead:
    expanded = await ai_search_service.expand_search_value(session, data.value, strict=True)
    return AiSearchExpandRead(original=data.value, expanded=expanded or data.value)


@router.get("/status", response_model=AiSearchStatusRead)
async def status(session: DbSession, user: CurrentUser) -> AiSearchStatusRead:
    return AiSearchStatusRead(available=await ai_search_service.is_available(session))


@router.get("/settings", response_model=AiSearchSettingsRead)
async def get_settings(session: DbSession, user: SuperAdmin) -> AiSearchSettingsRead:
    return ai_search_service.setting_read(await ai_search_service.get_setting(session))


@router.put("/settings", response_model=AiSearchSettingsRead)
async def update_settings(
    data: AiSearchSettingsUpdate, session: DbSession, user: SuperAdmin
) -> AiSearchSettingsRead:
    setting = await ai_search_service.update_setting(session, data)
    return ai_search_service.setting_read(setting)


@router.post("/settings/test", response_model=AiSearchTestRead)
async def test_settings(session: DbSession, user: SuperAdmin) -> AiSearchTestRead:
    original = "电机"
    expanded = await ai_search_service.test_search_value(session, original)
    return AiSearchTestRead(original=original, expanded=expanded or original)
