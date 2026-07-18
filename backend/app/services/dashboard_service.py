from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import PurchaseRequestStatus
from app.models import (
    PurchaseMaterial,
    PurchaseRequest,
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
                )
            )
        )
        or 0
    )
    pending_request = int(
        (
            await session.scalar(
                select(func.count(PurchaseRequest.id)).where(
                    PurchaseRequest.status.in_(
                        [PurchaseRequestStatus.SUBMITTED, PurchaseRequestStatus.PROCESSING]
                    )
                )
            )
        )
        or 0
    )
    partial = int(
        (
            await session.scalar(
                select(func.count(PurchaseRequest.id)).where(
                    PurchaseRequest.status == PurchaseRequestStatus.PARTIALLY_RECEIVED
                )
            )
        )
        or 0
    )
    # 急需申购/在途两项基于低库存列表计算；这里只按是否已有在途单据做摘要。
    from app.services.inventory_service import inventory_balances

    balances, _ = await inventory_balances(
        session,
        keyword=None,
        minimum_qty=None,
        maximum_qty=None,
        low_stock_only=True,
        page=1,
        page_size=max(low_count, 1),
    )
    pending_purchase = sum(item.warning_state == "PENDING_PURCHASE" for item in balances)
    on_order = sum(item.warning_state == "ON_ORDER" for item in balances)
    return DashboardSummaryRead(
        stock_material_count=stock_count,
        low_stock_count=low_count,
        pending_purchase_count=pending_purchase,
        on_order_count=on_order,
        uncoded_purchase_material_count=uncoded_count,
        pending_purchase_request_count=pending_request,
        partially_received_count=partial,
    )
