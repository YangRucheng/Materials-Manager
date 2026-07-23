from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import BusinessEventLog
from app.services import ai_search_service
from tests.conftest import auth_headers
from tests.integration.test_procurement import create_purchase_plan, move_to_record


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "choices": [
                {"message": {"content": '{"expansions":[["电机","电动机"]]}'}}
            ]
        }


class FakeAiClient:
    async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
        return FakeResponse()

    async def aclose(self) -> None:
        return None


class TimeoutAiClient:
    async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
        request = httpx.Request("POST", "https://example.test/v1/chat/completions")
        raise httpx.ReadTimeout("timed out", request=request)

    async def aclose(self) -> None:
        return None


class GlmResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "reasoning_content": "需要为电机补充常用规范名称。",
                        "content": '输出如下：\n{"expansions":["电机","电动机"]}',
                    }
                }
            ]
        }


class GlmAiClient:
    request_json: dict[str, Any] | None = None

    async def post(self, *_args: object, **kwargs: object) -> GlmResponse:
        self.request_json = kwargs.get("json") if isinstance(kwargs.get("json"), dict) else None
        return GlmResponse()

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_super_admin_configures_ai_search_and_key_is_returned_but_encrypted_at_rest(
    client: AsyncClient,
) -> None:
    admin = await auth_headers(client, "admin")
    purchase = await auth_headers(client, "purchase")

    forbidden = await client.get("/api/v1/ai-search/settings", headers=purchase)
    assert forbidden.status_code == 403

    saved = await client.put(
        "/api/v1/ai-search/settings",
        headers=admin,
        json={
            "endpoint": "https://example.test/v1/",
            "api_key": "secret-key",
            "model": "fast-model",
            "enabled": True,
            "version": 0,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == {
        "endpoint": "https://example.test/v1",
        "api_key": "secret-key",
        "model": "fast-model",
        "enabled": True,
        "updated_at": saved.json()["updated_at"],
        "version": 1,
    }
    assert "secret-key" in saved.text

    loaded = await client.get("/api/v1/ai-search/settings", headers=admin)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["api_key"] == "secret-key"

    status = await client.get("/api/v1/ai-search/status", headers=purchase)
    assert status.status_code == 200
    assert status.json() == {"available": True}

    async with SessionLocal() as session:
        event = await session.scalar(
            select(BusinessEventLog).where(
                BusinessEventLog.action == "AI_SEARCH_CONFIG_UPDATED"
            )
        )
        assert event is not None
        assert event.after_data is not None
        encrypted = event.after_data["api_key_encrypted"]
        assert encrypted != "secret-key"
        assert "secret-key" not in str(encrypted)


@pytest.mark.asyncio
async def test_ai_expansion_applies_to_plans_and_records(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    admin = await auth_headers(client, "admin")
    purchase = await auth_headers(client, "purchase")
    monkeypatch.setattr(ai_search_service, "_client", FakeAiClient())

    configured = await client.put(
        "/api/v1/ai-search/settings",
        headers=admin,
        json={
            "endpoint": "https://example.test/v1",
            "api_key": "secret-key",
            "model": "fast-model",
            "enabled": True,
            "version": 0,
        },
    )
    assert configured.status_code == 200, configured.text

    expanded = await client.post(
        "/api/v1/ai-search/expand",
        headers=purchase,
        json={"value": "电机"},
    )
    assert expanded.status_code == 200, expanded.text
    assert expanded.json() == {"original": "电机", "expanded": "电机|电动机"}

    motor = await create_purchase_plan(client, purchase, "电机", code="AI-001")
    electric_motor = await create_purchase_plan(client, purchase, "电动机", code="AI-002")

    normal = await client.get(
        "/api/v1/purchase-materials", headers=purchase, params={"name": "电机"}
    )
    empowered = await client.get(
        "/api/v1/purchase-materials",
        headers=purchase,
        params={"name": "电机", "ai_expand": True},
    )
    assert {item["id"] for item in normal.json()["items"]} == {motor["id"]}
    assert {item["id"] for item in empowered.json()["items"]} == {
        motor["id"],
        electric_motor["id"],
    }

    first_record = await move_to_record(client, purchase, int(motor["id"]), "AI-R-001")
    second_record = await move_to_record(
        client, purchase, int(electric_motor["id"]), "AI-R-002"
    )
    records = await client.get(
        "/api/v1/purchase-records",
        headers=purchase,
        params={"name": "电机", "ai_expand": True},
    )
    assert {item["line_id"] for item in records.json()["items"]} == {
        first_record["line_id"],
        second_record["line_id"],
    }


@pytest.mark.asyncio
async def test_ai_response_timeout_returns_specific_bad_request(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    admin = await auth_headers(client, "admin")
    monkeypatch.setattr(ai_search_service, "_client", TimeoutAiClient())

    configured = await client.put(
        "/api/v1/ai-search/settings",
        headers=admin,
        json={
            "endpoint": "https://example.test/v1",
            "api_key": "secret-key",
            "model": "slow-model",
            "enabled": True,
            "version": 0,
        },
    )
    assert configured.status_code == 200, configured.text

    response = await client.post("/api/v1/ai-search/settings/test", headers=admin)
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "AI_RESPONSE_TIMEOUT"
    assert "等待上游响应数据阶段" in response.json()["message"]
    assert "slow-model" in response.json()["message"]
    assert "https://example.test/v1/chat/completions" in response.json()["message"]
    assert response.json()["details"]["phase"] == "response_wait"
    assert response.json()["details"]["timeout_seconds"] == 30.0


@pytest.mark.asyncio
async def test_glm_models_disable_thinking_and_request_json_output(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    admin = await auth_headers(client, "admin")
    glm_client = GlmAiClient()
    monkeypatch.setattr(ai_search_service, "_client", glm_client)

    configured = await client.put(
        "/api/v1/ai-search/settings",
        headers=admin,
        json={
            "endpoint": "https://open.bigmodel.cn/api/paas/v4",
            "api_key": "secret-key",
            "model": "glm-4.7-flash",
            "enabled": True,
            "version": 0,
        },
    )
    assert configured.status_code == 200, configured.text

    response = await client.post("/api/v1/ai-search/settings/test", headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()["expanded"] == "电机|电动机"
    assert glm_client.request_json is not None
    assert glm_client.request_json["thinking"] == {"type": "disabled"}
    assert glm_client.request_json["response_format"] == {"type": "json_object"}
    assert glm_client.request_json["stream"] is False
    assert glm_client.request_json["messages"][0]["role"] == "system"
    assert "仅包含 1 个子数组" in glm_client.request_json["messages"][0]["content"]
    assert glm_client.request_json["messages"][1] == {
        "role": "user",
        "content": '{"input_terms": ["电机"]}',
    }
