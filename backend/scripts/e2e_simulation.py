"""端到端模拟用户操作脚本。

由 GitHub Actions（e2e-simulation.yml）在真实 MySQL + 后端实例上运行：
通过 HTTP 模拟四种角色用户的核心操作，验证主流程可用。任一步骤失败即以非零码退出。

用法：
    E2E_BASE_URL=http://127.0.0.1:8000 python scripts/e2e_simulation.py
"""

from __future__ import annotations

import os
import sys
import uuid

import httpx

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PASSWORD = "123456"


def _auth(client: httpx.Client, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError(f"登录 {username} 未返回 access_token")
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    run = uuid.uuid4().hex[:8]
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # 1. 健康检查（匿名）
        health = client.get("/health")
        assert health.status_code == 200 and health.json()["database"] == "ok", "健康检查失败"
        print("✅ 健康检查")

        # 2. 四种角色登录
        warehouse = _auth(client, "warehouse")
        purchase = _auth(client, "purchase")
        readonly = _auth(client, "readonly")
        admin = _auth(client, "admin")
        print("✅ 四种角色登录")

        # 3. 只读用户越权创建物资应 403
        denied = client.post(
            "/api/v1/stock-materials",
            headers=readonly,
            json={
                "name": f"E2E-越权-{run}",
                "model_spec": "E2E",
                "unit_name": "个",
                "image_ids": [],
            },
        )
        assert denied.status_code == 403, f"只读用户越权未被拒绝: {denied.text}"
        print("✅ 只读用户越权拦截")

        # 4. 仓库管理员创建物资
        material = client.post(
            "/api/v1/stock-materials",
            headers=warehouse,
            json={
                "name": f"E2E 测试物资 {run}",
                "model_spec": "E2E-MODEL",
                "unit_name": "个",
                "remark": "端到端模拟",
                "image_ids": [],
            },
        )
        assert material.status_code == 201, material.text
        material_id = material.json()["id"]
        print(f"✅ 创建物资 #{material_id}")

        # 5. 入库 10
        inbound = client.post(
            "/api/v1/inventory/inbounds",
            headers=warehouse,
            json={
                "client_request_id": uuid.uuid4().hex,
                "occurred_at": "2026-08-15T10:00:00+08:00",
                "source_type": "MANUAL",
                "business_reason": "E2E 入库",
                "lines": [{"stock_material_id": material_id, "quantity": "10"}],
            },
        )
        assert inbound.status_code == 201, inbound.text
        print("✅ 入库 10")

        # 6. 出库 3
        outbound = client.post(
            "/api/v1/inventory/outbounds",
            headers=warehouse,
            json={
                "client_request_id": uuid.uuid4().hex,
                "occurred_at": "2026-08-15T11:00:00+08:00",
                "source_type": "MANUAL",
                "business_reason": "E2E 出库",
                "receiver_name": "E2E 领用人",
                "lines": [{"stock_material_id": material_id, "quantity": "3"}],
            },
        )
        assert outbound.status_code == 201, outbound.text
        print("✅ 出库 3")

        # 7. 余额应为 7
        balance = client.get(f"/api/v1/inventory/balances/{material_id}", headers=warehouse)
        assert balance.status_code == 200, balance.text
        assert balance.json()["current_qty"] == "7", balance.json()
        print("✅ 余额 = 7")

        # 8. 库存列表查询
        inventory = client.get(
            "/api/v1/inventory/balances", headers=warehouse, params={"page": 1, "page_size": 20}
        )
        assert inventory.status_code == 200, inventory.text
        print("✅ 库存列表查询")

        # 9. 出入库记录查询
        records = client.get(
            "/api/v1/inventory/operations", headers=warehouse, params={"page": 1, "page_size": 20}
        )
        assert records.status_code == 200, records.text
        print("✅ 出入库记录查询")

        # 10. 申购管理员创建申购计划
        plan = client.post(
            "/api/v1/purchase-materials",
            headers=purchase,
            json={
                "plan_date": "2026-08-20",
                "name": f"E2E 申购物资 {run}",
                "model_spec": "E2E-MODEL",
                "unit_name": "个",
                "actual_demand_person": "E2E 需求人",
                "purchase_responsible": "E2E 负责人",
                "planned_qty": "5",
                "usage": "端到端模拟",
                "image_ids": [],
            },
        )
        assert plan.status_code == 201, plan.text
        print("✅ 创建申购计划")

        # 11. 超级管理员查询申购计划
        plans = client.get(
            "/api/v1/purchase-materials", headers=admin, params={"page": 1, "page_size": 20}
        )
        assert plans.status_code == 200, plans.text
        print("✅ 申购计划列表查询")

    print(f"🎉 模拟用户操作全部通过（run={run}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
