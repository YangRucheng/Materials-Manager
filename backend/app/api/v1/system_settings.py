from fastapi import APIRouter

from app.core.permissions import CurrentUser, DbSession
from app.schemas import ImageAccelerationSettingsRead, MiniProgramCodeSettingsRead
from app.services import ai_search_service

router = APIRouter(prefix="/system-settings", tags=["系统设置"])


@router.get("/image-acceleration", response_model=ImageAccelerationSettingsRead)
async def image_acceleration_settings(session: DbSession) -> ImageAccelerationSettingsRead:
    server_url = await ai_search_service.get_image_acceleration_server_url(session)
    return ImageAccelerationSettingsRead(image_acceleration_server_url=server_url)


@router.get("/mini-program-code", response_model=MiniProgramCodeSettingsRead)
async def mini_program_code_settings(
    session: DbSession, user: CurrentUser
) -> MiniProgramCodeSettingsRead:
    env = await ai_search_service.get_mini_program_code_env(session)
    return MiniProgramCodeSettingsRead(mini_program_code_env=env)
