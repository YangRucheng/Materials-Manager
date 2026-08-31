from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.mcp_server import mcp
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
        user = await session.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        # 库中只存哈希，明文通过重新生成接口一次性获取。
        token = (
            await client.post(
                "/api/v1/auth/login", json={"username": "admin", "password": "123456"}
            )
        ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    users = await client.get("/api/v1/users", headers=headers)
    admin_id = next(item["id"] for item in users.json()["items"] if item["username"] == "admin")
    admin_version = next(
        item["version"] for item in users.json()["items"] if item["username"] == "admin"
    )
    regenerated = await client.post(
        f"/api/v1/users/{admin_id}/api-token/regenerate",
        headers=headers,
        json={"version": admin_version},
    )
    assert regenerated.status_code == 200, regenerated.text
    token = regenerated.json()["api_token"]
    assert token

    # The MCP HTTP app is mounted as a sub-app, so Starlette never runs its
    # lifespan. Enter the session manager's run() (which creates the task group)
    # directly for this request, exactly as the SDK's lifespan wiring would.
    async with mcp.session_manager.run():
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
