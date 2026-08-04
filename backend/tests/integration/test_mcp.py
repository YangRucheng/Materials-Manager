from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import User

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def mcp_request(method: str, params: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }


async def test_mcp_streamable_http_requires_api_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/mcp/",
        headers=MCP_HEADERS,
        json=mcp_request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1"},
            },
        ),
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


async def test_mcp_streamable_http_lists_safe_tools_with_user_token(
    client: AsyncClient,
) -> None:
    async with SessionLocal() as session:
        token = await session.scalar(select(User.api_token).where(User.username == "admin"))
    assert token

    response = await client.post(
        "/api/v1/mcp/",
        headers={**MCP_HEADERS, "X-API-Token": token},
        json=mcp_request("tools/list"),
    )

    assert response.status_code == 200, response.text
    tools = response.json()["result"]["tools"]
    assert {item["name"] for item in tools} == {
        "system_whoami",
        "operations_list",
        "operation_describe",
        "operation_call",
    }
