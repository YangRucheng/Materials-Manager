from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import PurchasePlanStatus
from app.models import (
    PurchaseMaterial,
    PurchaseRequestLine,
    StockBalance,
    StockMaterial,
    StockReplenishmentPolicy,
)
from app.schemas import DashboardSummaryRead


async def dashboard_summary(session: AsyncSession) -> DashboardSummaryRead:
    stock_count = int((await session.scalar(select(func.count(StockMaterial.id)))) or 0)
    low_count = int(
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
    uncoded_count = int(
        (
            await session.scalar(
                select(func.count(PurchaseMaterial.id)).where(
                    PurchaseMaterial.material_code.is_(None),
                    PurchaseMaterial.enabled.is_(True),
                    PurchaseMaterial.status == PurchasePlanStatus.NORMAL,
                )
            )
        )
        or 0
    )
    purchase_record_count = int(
        (await session.scalar(select(func.count(PurchaseRequestLine.id)))) or 0
    )
    return DashboardSummaryRead(
        stock_material_count=stock_count,
        low_stock_count=low_count,
        uncoded_purchase_material_count=uncoded_count,
        purchase_record_count=purchase_record_count,
    )
