from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import PurchaseMaterial
from app.schemas import PurchaseMaterialCreate
from app.services import material_service


@pytest.mark.asyncio
async def test_create_purchase_material_retries_plan_no_on_collision() -> None:
    """并发同日创建撞 uq_purchase_material_plan_no 时，保存点重试应得到新序号。"""
    from app.core.database import Base, engine

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        first = await material_service.create_purchase_material(
            session,
            PurchaseMaterialCreate(
                plan_date=date(2026, 8, 1),
                category="备品备件",
                name="重试测试物资",
                model_spec="RETRY-1",
                unit_name="个",
                planned_qty="1",
                usage="测试",
                actual_demand_person="张三",
            ),
        )
        await session.commit()
        first_no = first.plan_no

        # 模拟并发：第二次创建拿到与 first 相同的序号（MAX+1 竞态），再撞唯一约束。
        real = material_service.next_purchase_plan_no
        calls = {"count": 0}

        async def colliding_plan_no(session, plan_date):
            calls["count"] += 1
            if calls["count"] == 1:
                return first_no
            return await real(session, plan_date)

        material_service.next_purchase_plan_no = colliding_plan_no
        try:
            second = await material_service.create_purchase_material(
                session,
                PurchaseMaterialCreate(
                    plan_date=date(2026, 8, 1),
                    category="备品备件",
                    name="重试测试物资2",
                    model_spec="RETRY-2",
                    unit_name="个",
                    planned_qty="2",
                    usage="测试",
                    actual_demand_person="李四",
                ),
            )
        finally:
            material_service.next_purchase_plan_no = real
        await session.commit()

        assert second.plan_no != first_no
        assert second.id != first.id
        stored = list(
            (
                await session.scalars(
                    select(PurchaseMaterial).where(PurchaseMaterial.plan_date == date(2026, 8, 1))
                )
            ).all()
        )
        assert len(stored) == 2
        assert {item.plan_no for item in stored} == {first_no, second.plan_no}