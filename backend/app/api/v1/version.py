from fastapi import APIRouter

from app.core.config import settings
from app.schemas import VersionInfoRead

router = APIRouter(tags=["版本信息"])


@router.get("/version", response_model=VersionInfoRead, summary="应用版本与后端构建信息")
async def version_info() -> VersionInfoRead:
    """返回应用名、版本号、git 提交与后端镜像构建时间（供前端关于页展示）。"""
    return VersionInfoRead(
        app_name=settings.app_name,
        version="1.0.0",
        commit=settings.git_sha,
        build_time=settings.build_time,
    )
