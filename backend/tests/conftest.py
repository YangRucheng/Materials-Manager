from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

os.environ["APP_DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ["APP_JWT_SECRET"] = "test-secret-that-is-long-enough-123456"
os.environ["APP_WECHAT_MINI_PROGRAM_APP_ID"] = "wx-test-primary,wx-test-secondary"
os.environ["APP_WECHAT_MINI_PROGRAM_APP_SECRET"] = (
    "test-primary-secret,test-secondary-secret"
)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.domain.enums import Role
from app.main import app
from app.models import User

settings.template_dir = Path(__file__).parents[1] / "app" / "templates"


@pytest_asyncio.fixture
async def client(tmp_path) -> AsyncIterator[AsyncClient]:
    settings.upload_dir = tmp_path / "uploads"
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        session.add_all(
            [
                User(
                    username="admin",
                    password_hash=hash_password("123456"),
                    display_name="系统管理员",
                    role=Role.SUPER_ADMIN,
                    enabled=True,
                ),
                User(
                    username="warehouse",
                    password_hash=hash_password("123456"),
                    display_name="仓库管理员",
                    role=Role.WAREHOUSE_ADMIN,
                    enabled=True,
                ),
                User(
                    username="purchase",
                    password_hash=hash_password("123456"),
                    display_name="申购管理员",
                    role=Role.PURCHASE_ADMIN,
                    enabled=True,
                ),
                User(
                    username="readonly",
                    password_hash=hash_password("123456"),
                    display_name="只读用户",
                    role=Role.READ_ONLY,
                    enabled=True,
                ),
            ]
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def auth_headers(client: AsyncClient, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": "123456"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_stock(
    client: AsyncClient, headers: dict[str, str], name: str = "交流接触器"
) -> int:
    response = await client.post(
        "/api/v1/stock-materials",
        headers=headers,
        json={
            "name": name,
            "model_spec": "CJX2-2510 220V",
            "unit_name": "个",
            "remark": "测试",
            "image_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])
