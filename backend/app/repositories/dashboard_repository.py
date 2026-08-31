"""仪表盘聚合计数的持久化查询边界。

只承载纯 SELECT 聚合查询，不组装 read、不自建 session。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import PurchasePlanStatus
from app.models import (
    LiteInventory,
    PurchaseMaterial,
    PurchaseRequestLine,
    StockBalance,
    StockMaterial,
    StockReplenishmentPolicy,
)


async def count_stock_materials(session: AsyncSession) -> int:
    return int((await session.scalar(select(func.count(StockMaterial.id)))) or 0)


async def count_lite_inventory(session: AsyncSession) -> int:
    """精简二级库行数（二级库精简模式下工作台“二级库物资”统计用）。"""
    return int((await session.scalar(select(func.count(LiteInventory.id)))) or 0)


async def count_low_stock_materials(session: AsyncSession) -> int:
    return int(
        (
            await session.scalar(
                select(func.count(StockMaterial.id))
                .join(StockBalance)
                .join(StockReplenishmentPolicy)
                .where(
                    StockReplenishmentPolicy.enabled.is_(True),
                    StockBalance.quantity <= StockReplenishmentPolicy.minimum_qty,
                )
            )
        )
        or 0
    )


async def count_uncoded_purchase_materials(session: AsyncSession) -> int:
    return int(
        (
            await session.scalar(
                select(func.count(PurchaseMaterial.id)).where(
                    PurchaseMaterial.material_code.is_(None),
                    PurchaseMaterial.status == PurchasePlanStatus.NORMAL,
                )
            )
        )
        or 0
    )


async def count_purchase_records(session: AsyncSession) -> int:
    return int((await session.scalar(select(func.count(PurchaseRequestLine.id)))) or 0)
