from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.domain.enums import OperationType, Role, SourceType
from app.models import (
    MeasurementUnit,
    ProjectSubitem,
    PurchaseMaterial,
    StockBalance,
    StockMaterial,
    StockReplenishmentPolicy,
    User,
)
from app.schemas import OperationCreate, OperationLineWrite
from app.services.common import identity_hash
from app.services.inventory_service import create_operation

USERS = [
    ("admin", "系统管理员", Role.SUPER_ADMIN),
    ("warehouse", "仓库管理员", Role.WAREHOUSE_ADMIN),
    ("purchase", "申购管理员", Role.PURCHASE_ADMIN),
    ("readonly", "只读用户", Role.READ_ONLY),
]
UNITS = [("PCS", "件", 0), ("SET", "套", 0), ("M", "米", 2), ("KG", "千克", 3)]
PROJECTS = [
    ("WX-2026", "2026 年度检修", "01-01", "1#机组控制柜检修"),
    ("WX-2026", "2026 年度检修", "01-02", "2#机组控制柜检修"),
    ("DX-2026", "电气专项", "03-01", "配电室改造"),
]
STOCK = [
    ("交流接触器", "CJX2-2510 220V", "PCS", "控制柜常用", "2", "3", "10"),
    ("小型断路器", "C65N-C16/2P", "PCS", None, "8", "5", "15"),
    ("铜芯控制电缆", "KVV 4×1.5mm²", "M", None, "18.5", "20", "100"),
    ("绝缘胶带", "18mm×20m 黑色", "PCS", None, "35", "10", "40"),
]


async def seed() -> None:
    async with SessionLocal() as session:
        if await session.scalar(select(User.id).limit(1)):
            return
        users = [
            User(
                username=username,
                password_hash=hash_password("123456"),
                display_name=name,
                role=role,
                enabled=True,
            )
            for username, name, role in USERS
        ]
        session.add_all(users)
        await session.flush()
        admin_id = users[0].id
        units = {
            code: MeasurementUnit(
                code=code,
                name=name,
                decimal_places=places,
                enabled=True,
                created_by=admin_id,
                updated_by=admin_id,
            )
            for code, name, places in UNITS
        }
        session.add_all(units.values())
        session.add_all(
            [
                ProjectSubitem(
                    project_code=project_code,
                    project_name=project_name,
                    subitem_no=subitem_no,
                    subitem_name=subitem_name,
                    enabled=True,
                    created_by=admin_id,
                    updated_by=admin_id,
                )
                for project_code, project_name, subitem_no, subitem_name in PROJECTS
            ]
        )
        await session.flush()
        stock_items: list[StockMaterial] = []
        for name, spec, unit_code, remark, _qty, minimum, target in STOCK:
            unit = units[unit_code]
            item = StockMaterial(
                name=name,
                model_spec=spec,
                unit_id=unit.id,
                remark=remark,
                identity_hash=identity_hash(name, spec, unit.id),
                enabled=True,
                created_by=admin_id,
                updated_by=admin_id,
            )
            item.balance = StockBalance(quantity=Decimal("0"))
            item.replenishment_policy = StockReplenishmentPolicy(
                minimum_qty=Decimal(minimum),
                target_qty=Decimal(target),
                enabled=True,
                created_by=admin_id,
                updated_by=admin_id,
            )
            session.add(item)
            stock_items.append(item)
        await session.flush()
        await create_operation(
            session,
            OperationCreate(
                client_request_id="seed-initialization-20260717",
                occurred_at=datetime(2026, 7, 17, tzinfo=UTC),
                source_type=SourceType.INITIALIZATION,
                business_reason="系统种子数据初始化入库",
                lines=[
                    OperationLineWrite(stock_material_id=item.id, quantity=Decimal(seed[4]))
                    for item, seed in zip(stock_items, STOCK, strict=True)
                ],
            ),
            OperationType.INBOUND,
            admin_id,
        )
        session.add_all(
            [
                PurchaseMaterial(
                    material_code="DQ-000101",
                    name=stock_items[0].name,
                    model_spec=stock_items[0].model_spec,
                    unit_id=stock_items[0].unit_id,
                    stock_material_id=stock_items[0].id,
                    identity_hash=stock_items[0].identity_hash,
                    enabled=True,
                    created_by=admin_id,
                    updated_by=admin_id,
                ),
                PurchaseMaterial(
                    name="智能电机保护器",
                    model_spec="M60-2P 5A",
                    unit_id=units["PCS"].id,
                    remark="新物资",
                    identity_hash=identity_hash("智能电机保护器", "M60-2P 5A", units["PCS"].id),
                    enabled=True,
                    created_by=admin_id,
                    updated_by=admin_id,
                ),
                PurchaseMaterial(
                    material_code="DQ-000188",
                    name="温湿度控制器",
                    model_spec="WSK-SH",
                    unit_id=units["PCS"].id,
                    identity_hash=identity_hash("温湿度控制器", "WSK-SH", units["PCS"].id),
                    enabled=True,
                    created_by=admin_id,
                    updated_by=admin_id,
                ),
            ]
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
