from uuid import UUID

import pytest

from app.core.errors import AppError
from app.domain.enums import MiniProgramCodeEnv
from app.services import mini_program_service


@pytest.mark.asyncio
async def test_generate_unlimited_material_code_uses_compact_uuid_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    material_uuid = UUID("10000000-0000-4000-8000-000000000001")
    captured: list[dict[str, object]] = []

    async def fake_access_token() -> str:
        return "wechat-access-token"

    class FakeResponse:
        headers = {"content-type": "image/png"}

        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url, *, params, json):
            captured.append({"url": url, "params": params, "json": json})
            return FakeResponse(f"png-{json['env_version']}".encode())

    monkeypatch.setattr(mini_program_service, "_get_wechat_access_token", fake_access_token)
    monkeypatch.setattr(
        mini_program_service.httpx,
        "AsyncClient",
        lambda **_kwargs: FakeClient(),
    )
    mini_program_service._material_code_cache.clear()

    trial = await mini_program_service.generate_unlimited_material_code(
        material_uuid, MiniProgramCodeEnv.TRIAL
    )
    repeated_trial = await mini_program_service.generate_unlimited_material_code(
        material_uuid, MiniProgramCodeEnv.TRIAL
    )
    release = await mini_program_service.generate_unlimited_material_code(
        material_uuid, MiniProgramCodeEnv.RELEASE
    )

    assert trial == repeated_trial == b"png-trial"
    assert release == b"png-release"
    assert captured == [
        {
            "url": "https://api.weixin.qq.com/wxa/getwxacodeunlimit",
            "params": {"access_token": "wechat-access-token"},
            "json": {
                "scene": "10000000000040008000000000000001",
                "page": "pages/outbound/outbound",
                "check_path": False,
                "env_version": "trial",
                "width": 430,
            },
        },
        {
            "url": "https://api.weixin.qq.com/wxa/getwxacodeunlimit",
            "params": {"access_token": "wechat-access-token"},
            "json": {
                "scene": "10000000000040008000000000000001",
                "page": "pages/outbound/outbound",
                "check_path": False,
                "env_version": "release",
                "width": 430,
            },
        },
    ]


@pytest.mark.asyncio
async def test_exchange_wechat_code_selects_credentials_by_app_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"openid": "secondary-openid"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, url, *, params):
            captured.update({"url": url, "params": params})
            return FakeResponse()

    monkeypatch.setattr(
        mini_program_service.httpx,
        "AsyncClient",
        lambda **_kwargs: FakeClient(),
    )

    app_id, openid = await mini_program_service.exchange_wechat_code(
        "temporary-code", "wx-test-secondary"
    )

    assert (app_id, openid) == ("wx-test-secondary", "secondary-openid")
    assert captured["params"] == {
        "appid": "wx-test-secondary",
        "secret": "test-secondary-secret",
        "js_code": "temporary-code",
        "grant_type": "authorization_code",
    }
    with pytest.raises(AppError, match="当前微信小程序登录尚未配置"):
        await mini_program_service.exchange_wechat_code("temporary-code", "wx-unknown")

    monkeypatch.setattr(
        mini_program_service.settings,
        "wechat_mini_program_app_id",
        "wx-test-primary, wx-test-secondary, wx-test-third",
    )
    monkeypatch.setattr(
        mini_program_service.settings,
        "wechat_mini_program_app_secret",
        "test-primary-secret, test-secondary-secret, test-third-secret",
    )
    third_app_id, _ = await mini_program_service.exchange_wechat_code(
        "third-code", "wx-test-third"
    )
    assert third_app_id == "wx-test-third"
    assert captured["params"]["secret"] == "test-third-secret"

    monkeypatch.setattr(
        mini_program_service.settings,
        "wechat_mini_program_app_secret",
        "test-primary-secret,test-secondary-secret",
    )
    with pytest.raises(AppError, match="AppID 与 AppSecret 配置无效"):
        await mini_program_service.exchange_wechat_code("temporary-code", "wx-test-primary")
