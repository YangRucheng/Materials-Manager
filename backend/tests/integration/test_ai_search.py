from __future__ import annotations

from typing import Any

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


@pytest.mark.asyncio
async def test_super_admin_configures_ai_search_and_key_is_not_exposed(
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
            "clear_api_key": False,
            "version": 0,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == {
        "endpoint": "https://example.test/v1",
        "model": "fast-model",
        "enabled": True,
        "api_key_configured": True,
        "updated_at": saved.json()["updated_at"],
        "version": 1,
    }
    assert "secret-key" not in saved.text

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
            "clear_api_key": False,
            "version": 0,
        },
    )
    assert configured.status_code == 200, configured.text

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
