"""version 接口冒烟测试：公开返回应用名/版本/构建信息，无需鉴权。"""

import pytest

pytestmark = pytest.mark.asyncio


async def test_version_endpoint(client) -> None:
    response = await client.get("/api/v1/version")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["app_name"] == "电气车间备件管理系统"
    assert body["version"] == "1.0.0"
    # 本地/测试环境未注入构建信息时为空；字段存在即可
    assert "commit" in body
    assert "build_time" in body
