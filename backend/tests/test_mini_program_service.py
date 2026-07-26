from uuid import UUID

import pytest

from app.services import mini_program_service


@pytest.mark.asyncio
async def test_generate_unlimited_material_code_uses_compact_uuid_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    material_uuid = UUID("10000000-0000-4000-8000-000000000001")
    captured: dict[str, object] = {}

    async def fake_access_token() -> str:
        return "wechat-access-token"

    class FakeResponse:
        headers = {"content-type": "image/png"}
        content = b"png-content"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url, *, params, json):
            captured.update(url=url, params=params, json=json)
            return FakeResponse()

    monkeypatch.setattr(mini_program_service, "_get_wechat_access_token", fake_access_token)
    monkeypatch.setattr(
        mini_program_service.httpx,
        "AsyncClient",
        lambda **_kwargs: FakeClient(),
    )
    mini_program_service._material_code_cache.pop(str(material_uuid), None)

    result = await mini_program_service.generate_unlimited_material_code(material_uuid)

    assert result == b"png-content"
    assert captured == {
        "url": "https://api.weixin.qq.com/wxa/getwxacodeunlimit",
        "params": {"access_token": "wechat-access-token"},
        "json": {
            "scene": "10000000000040008000000000000001",
            "page": "pages/outbound/index",
            "check_path": False,
            "width": 430,
        },
    }
