from __future__ import annotations

import pytest
from httpx import AsyncClient


def agent_headers(username: str = "admin", password: str = "123456") -> dict[str, str]:
    return {
        "X-Agent-Username": username,
        "X-Agent-Password": password,
    }


@pytest.mark.asyncio
async def test_agent_database_reads_schema_and_parameterized_data(client: AsyncClient) -> None:
    schema = await client.get("/api/v1/agent/database/schema", headers=agent_headers())
    assert schema.status_code == 200, schema.text
    assert schema.headers["cache-control"] == "no-store"
    tables = {item["name"]: item for item in schema.json()["tables"]}
    assert "user" in tables
    assert {column["name"] for column in tables["user"]["columns"]} >= {
        "id",
        "username",
        "role",
    }

    response = await client.post(
        "/api/v1/agent/database/execute",
        headers=agent_headers(),
        json={
            "sql": "SELECT id, username, role FROM user WHERE username = :username",
            "parameters": {"username": "warehouse"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "statement_type": "SELECT",
        "columns": ["id", "username", "role"],
        "rows": [{"id": 2, "username": "warehouse", "role": "WAREHOUSE_ADMIN"}],
        "row_count": 1,
        "affected_rows": None,
        "last_insert_id": None,
        "truncated": False,
    }

    limited = await client.post(
        "/api/v1/agent/database/execute",
        headers=agent_headers(),
        json={"sql": "SELECT id FROM user ORDER BY id", "max_rows": 1},
    )
    assert limited.status_code == 200, limited.text
    assert limited.json()["rows"] == [{"id": 1}]
    assert limited.json()["truncated"] is True


@pytest.mark.asyncio
async def test_agent_database_writes_all_application_tables(client: AsyncClient) -> None:
    inserted = await client.post(
        "/api/v1/agent/database/execute",
        headers=agent_headers(),
        json={
            "sql": (
                "INSERT INTO measurement_unit "
                "(code, name, decimal_places, enabled, created_at, updated_at, "
                "created_by, updated_by, version) "
                "VALUES (:code, :name, 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, 1, 1)"
            ),
            "parameters": {"code": "BOX", "name": "箱"},
        },
    )
    assert inserted.status_code == 200, inserted.text
    assert inserted.json()["statement_type"] == "INSERT"
    assert inserted.json()["affected_rows"] == 1

    updated = await client.post(
        "/api/v1/agent/database/execute",
        headers=agent_headers(),
        json={
            "sql": "UPDATE measurement_unit SET name = :name WHERE code = :code",
            "parameters": {"code": "BOX", "name": "  整箱  "},
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["affected_rows"] == 1

    selected = await client.post(
        "/api/v1/agent/database/execute",
        headers=agent_headers(),
        json={
            "sql": "SELECT name FROM measurement_unit WHERE code = :code",
            "parameters": {"code": "BOX"},
        },
    )
    assert selected.json()["rows"] == [{"name": "  整箱  "}]

    deleted = await client.post(
        "/api/v1/agent/database/execute",
        headers=agent_headers(),
        json={
            "sql": "DELETE FROM measurement_unit WHERE code = :code",
            "parameters": {"code": "BOX"},
        },
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["affected_rows"] == 1


@pytest.mark.asyncio
async def test_agent_database_requires_super_admin_password_headers(client: AsyncClient) -> None:
    for headers in (
        {},
        agent_headers(password="wrong-password"),
        agent_headers(username="warehouse"),
    ):
        response = await client.post(
            "/api/v1/agent/database/execute",
            headers=headers,
            json={"sql": "SELECT id FROM user"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_AGENT_DATABASE_CREDENTIALS"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE forbidden (id INT)",
        "ALTER TABLE user ADD COLUMN forbidden INT",
        "DROP TABLE user",
        "SELECT id FROM user; DELETE FROM user",
        "SELECT id FROM user -- comment",
        "SELECT id FROM user INTO OUTFILE '/tmp/users.csv'",
    ],
)
async def test_agent_database_rejects_ddl_multi_statement_and_server_files(
    client: AsyncClient,
    sql: str,
) -> None:
    response = await client.post(
        "/api/v1/agent/database/execute",
        headers=agent_headers(),
        json={"sql": sql},
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "AGENT_DATABASE_SQL_FORBIDDEN"
