from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import dashboard_repository
from app.schemas import DashboardSummaryRead


async def dashboard_summary(session: AsyncSession) -> DashboardSummaryRead:
    stock_count = await dashboard_repository.count_stock_materials(session)
    low_count = await dashboard_repository.count_low_stock_materials(session)
    uncoded_count = await dashboard_repository.count_uncoded_purchase_materials(session)
    purchase_record_count = await dashboard_repository.count_purchase_records(session)
    return DashboardSummaryRead(
        stock_material_count=stock_count,
        low_stock_count=low_count,
        uncoded_purchase_material_count=uncoded_count,
        purchase_record_count=purchase_record_count,
    )
