
from fastapi import APIRouter, Response, status

from app.core.permissions import CurrentUser, DbSession
from app.schemas import FileId, ShareCreateRequest, SharePublicView, ShareRead
from app.services import share_link_service

router = APIRouter(prefix="/shares", tags=["链接分享"])


@router.post("", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
async def create_share(
    data: ShareCreateRequest,
    session: DbSession,
    user: CurrentUser,
) -> ShareRead:
    """创建匿名分享链接：把勾选的申购计划/申购记录分享为无鉴权页面。

    失效时间由前端在二次确认时选择（24小时/3天/7天/30天/永久）。
    返回 token 与失效时间，前端据此拼接分享页 URL（/share/{token}）。
    """
    share = await share_link_service.create_share(
        session,
        share_type=data.share_type,
        item_ids=data.item_ids,
        expires_in=data.expires_in,
        created_by=user.id,
    )
    return ShareRead(
        token=share.token,
        share_type=share.share_type,
        item_count=len(share.item_ids),
        expires_at=share.expires_at,
        created_at=share.created_at,
    )


@router.get("/{token}", response_model=SharePublicView)
async def get_share(token: FileId, session: DbSession) -> SharePublicView:
    # 匿名读取是刻意设计：分享页无需登录，任何拿到链接的人都能查看。
    # 安全性依赖 token 为 UUIDv7（不可猜解）+ 仅按 token 返回该分享的数据快照，
    # 与图片匿名读取 / 导出文件匿名下载同一信任模型（见 files.py / excel_export_jobs.py 注释）。
    return await share_link_service.get_public_share(session, token=token)


@router.delete("/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    token: FileId,
    session: DbSession,
    user: CurrentUser,
) -> Response:
    """撤回分享：仅创建者本人或超级管理员可执行，撤回后匿名读取立即失效。"""
    await share_link_service.revoke_share(session, token=token, user=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
