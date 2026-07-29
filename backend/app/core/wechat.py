from __future__ import annotations

from app.core.config import settings
from app.core.errors import AppError


def configured_wechat_app_ids() -> list[str]:
    return list(
        dict.fromkeys(
            item.strip()
            for item in settings.wechat_mini_program_app_id.split(",")
            if item.strip()
        )
    )


def get_wechat_credentials(app_id: str | None) -> tuple[str, str]:
    app_ids = [
        item.strip()
        for item in settings.wechat_mini_program_app_id.split(",")
        if item.strip()
    ]
    app_secrets = [
        item.strip()
        for item in settings.wechat_mini_program_app_secret.split(",")
        if item.strip()
    ]
    if not app_ids or len(app_ids) != len(app_secrets) or len(app_ids) != len(set(app_ids)):
        raise AppError(
            "WECHAT_CONFIGURATION_INVALID",
            "微信小程序 AppID 与 AppSecret 配置无效",
            status_code=503,
            details={
                "app_id_count": len(app_ids),
                "app_secret_count": len(app_secrets),
            },
        )

    effective_app_id = app_id or app_ids[0]
    try:
        app_secret = app_secrets[app_ids.index(effective_app_id)]
    except ValueError as exc:
        raise AppError(
            "WECHAT_NOT_CONFIGURED",
            "当前微信小程序登录尚未配置",
            status_code=503,
            details={"app_id": effective_app_id or None},
        ) from exc
    return effective_app_id, app_secret
