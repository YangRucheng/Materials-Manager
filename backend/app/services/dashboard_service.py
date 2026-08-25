from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import dashboard_repository
from app.schemas import DashboardSummaryRead
from app.services import ai_search_service


async def dashboard_summary(session: AsyncSession) -> DashboardSummaryRead:
    # 二级库精简模式下：物资数取精简表行数，且无安全库存概念（低库存计 0）。
    if await ai_search_service.is_lite_secondary_warehouse(session):
        stock_count = await dashboard_repository.count_lite_inventory(session)
        low_count = 0
    else:
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
