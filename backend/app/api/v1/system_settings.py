from fastapi import APIRouter

from app.core.permissions import CurrentUser, DbSession
from app.schemas import MiniProgramCodeSettingsRead
from app.services import ai_search_service

router = APIRouter(prefix="/system-settings", tags=["系统设置"])


@router.get("/mini-program-code", response_model=MiniProgramCodeSettingsRead)
async def mini_program_code_settings(
    session: DbSession, user: CurrentUser
) -> MiniProgramCodeSettingsRead:
    env = await ai_search_service.get_mini_program_code_env(session)
    return MiniProgramCodeSettingsRead(mini_program_code_env=env)
