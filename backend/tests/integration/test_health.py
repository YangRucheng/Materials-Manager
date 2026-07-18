from __future__ import annotations

from typing import Self

from httpx import AsyncClient
from pytest import MonkeyPatch

from app import main


class FailingConnection:
    async def __aenter__(self) -> Self:
        raise RuntimeError("database unavailable")

    async def __aexit__(self, *_args: object) -> None:
        return None


class FailingEngine:
    def connect(self) -> FailingConnection:
        return FailingConnection()


async def test_health_checks_database(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_reports_database_failure(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "engine", FailingEngine())

    response = await client.get("/health")

    assert response.status_code == 503
    assert response.json()["code"] == "DATABASE_UNAVAILABLE"


async def test_health_reports_schema_mismatch(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    differences = {"missing_tables": ["purchase_material"]}
    monkeypatch.setattr(main, "schema_differences", lambda _connection: differences)

    response = await client.get("/health")

    assert response.status_code == 503
    assert response.json()["code"] == "DATABASE_SCHEMA_MISMATCH"
    assert response.json()["details"] == differences
