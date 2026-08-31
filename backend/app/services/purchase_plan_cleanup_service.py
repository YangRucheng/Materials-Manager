"""申购计划清理后台任务。

每天凌晨 2 点（北京时间）删除已转入申购记录的申购计划，消除计划表冗余留存。

记录转入时已把计划全部业务字段快照到 purchase_request_line（含镜像），读路径
不再依赖计划表，因此删除计划是安全的。删除前先将记录行 purchase_material_id
置空（解绑外键），再物理删除计划。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update

from app.core.constants import SHANGHAI
from app.core.database import SessionLocal
from app.models import PurchaseMaterial, PurchaseRequestLine

logger = logging.getLogger(__name__)

_CLEANUP_HOUR = 2
_BATCH_SIZE = 50


def _seconds_until_two_am(now: datetime) -> float:
    """距下一个凌晨 2 点（北京时间）的秒数。纯函数便于单测。"""
    target = now.replace(hour=_CLEANUP_HOUR, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def cleanup_moved_plans_once() -> int:
    """删除一批已转入申购记录的计划，返回删除数。幂等：无候选立即返回 0。

    迁移护栏：仅清理被引用的行快照已回填（plan_no_snapshot 非空）的计划，
    防止旧库未迁移时误删导致记录字段缺失。
    """
    async with SessionLocal() as session:
        candidate_ids = list(
            (
                await session.scalars(
                    select(PurchaseMaterial.id)
                    .join(
                        PurchaseRequestLine,
                        PurchaseRequestLine.purchase_material_id == PurchaseMaterial.id,
                    )
                    .where(
                        PurchaseRequestLine.plan_no_snapshot.is_not(None),
                        func.trim(PurchaseRequestLine.plan_no_snapshot) != "",
                    )
                    .distinct()
                    .order_by(PurchaseMaterial.id)
                    .limit(_BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if not candidate_ids:
            return 0
        await session.execute(
            update(PurchaseRequestLine)
            .where(PurchaseRequestLine.purchase_material_id.in_(candidate_ids))
            .values(purchase_material_id=None)
        )
        await session.execute(
            sa_delete(PurchaseMaterial).where(PurchaseMaterial.id.in_(candidate_ids))
        )
        await session.commit()
        logger.info(
            "cleaned moved purchase plans count=%s ids=%s",
            len(candidate_ids),
            candidate_ids,
        )
        return len(candidate_ids)


async def run_cleanup_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=_seconds_until_two_am(datetime.now(SHANGHAI)),
            )
            break
        except TimeoutError:
            pass
        try:
            while await cleanup_moved_plans_once() > 0:
                pass
        except Exception:
            logger.exception("purchase plan cleanup iteration failed")
