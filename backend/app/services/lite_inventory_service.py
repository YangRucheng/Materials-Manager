from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import LiteInventory
from app.schemas import LiteInventoryRead
from app.services.common import contains_any
from app.services.import_file_reader import read_tabular_rows

EXPECTED_HEADERS = (
    "物资名称",
    "型号规格",
    "单位",
    "数量",
    "备注",
)
MAX_IMPORT_BYTES = 50 * 1024 * 1024
INSERT_BATCH_SIZE = 2_000
# 全字段相同视为重复行：上游报表常含重复行，逐字导成一条即可（保留行号提示）。
DEDUPE_FIELDS = ("name", "model_spec", "unit_name", "quantity", "remark")


def _dedupe_key(row: dict[str, object]) -> tuple[object, ...]:
    return tuple(row[field] for field in DEDUPE_FIELDS)


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _cell_quantity(value: object, *, row_number: int) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise AppError(
            "LITE_IMPORT_INVALID_QUANTITY",
            f"第 {row_number} 行数量不是有效数值",
            details={"row": row_number},
        ) from exc


def _validate_length(value: str, maximum: int, *, row_number: int, header: str) -> None:
    if len(value) > maximum:
        raise AppError(
            "LITE_IMPORT_VALUE_TOO_LONG",
            f"第 {row_number} 行“{header}”超过 {maximum} 个字符",
            details={"row": row_number, "column": header, "max_length": maximum},
        )


def parse_lite_file(path: Path) -> list[dict[str, object]]:
    rows = read_tabular_rows(path)

    header_row_index = 0
    header_indexes: dict[str, int] = {}
    for index in range(min(20, len(rows))):
        headers = [_cell_text(cell) for cell in rows[index]]
        indexes = {header: i for i, header in enumerate(headers) if header}
        if all(header in indexes for header in EXPECTED_HEADERS):
            header_row_index = index
            header_indexes = {header: indexes[header] for header in EXPECTED_HEADERS}
            break
    if not header_indexes:
        raise AppError(
            "LITE_IMPORT_HEADERS_MISSING",
            "表格缺少必需列：物资名称、型号规格、单位、数量、备注",
        )

    parsed: list[dict[str, object]] = []
    for index in range(header_row_index + 1, len(rows)):
        row_number = index + 1
        row = rows[index]
        values = {
            header: _cell_text(row[column]) if column < len(row) else ""
            for header, column in header_indexes.items()
        }
        if not any(values.values()):
            continue
        name = values["物资名称"]
        if not name:
            raise AppError(
                "LITE_IMPORT_NAME_REQUIRED",
                f"第 {row_number} 行缺少物资名称",
                details={"row": row_number},
            )
        _validate_length(name, 128, row_number=row_number, header="物资名称")
        _validate_length(values["型号规格"], 255, row_number=row_number, header="型号规格")
        _validate_length(values["单位"], 32, row_number=row_number, header="单位")
        _validate_length(values["备注"], 1000, row_number=row_number, header="备注")
        parsed.append(
            {
                "name": name,
                "model_spec": values["型号规格"] or None,
                "unit_name": values["单位"] or None,
                "quantity": _cell_quantity(values["数量"], row_number=row_number),
                "remark": values["备注"] or None,
            }
        )
    if not parsed:
        raise AppError("LITE_IMPORT_EMPTY", "表格中没有可导入的二级库数据")
    return parsed


async def process_import_file(file_path: Path) -> dict[str, object]:
    """异步导入处理器：解析（线程池）→ 全量替换 lite_inventory → 返回导入条数与去重统计。"""
    rows = await asyncio.to_thread(parse_lite_file, file_path)
    return await _replace_rows(rows)


async def _replace_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    """全量替换精简二级库表；完全重复的行只保留一条。"""
    seen: set[tuple[object, ...]] = set()
    deduplicated: list[dict[str, object]] = []
    for row in rows:
        key = _dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(row)
    async with SessionLocal() as session:
        await session.execute(delete(LiteInventory))
        for offset in range(0, len(deduplicated), INSERT_BATCH_SIZE):
            batch = deduplicated[offset : offset + INSERT_BATCH_SIZE]
            await session.execute(insert(LiteInventory), batch)
        await session.commit()
    return {
        "imported_count": len(deduplicated),
        "deduplicated_count": len(rows) - len(deduplicated),
    }


async def search_lite_inventory(
    session: AsyncSession,
    *,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[LiteInventoryRead], int]:
    query = select(LiteInventory)
    keyword_condition = contains_any(
        (LiteInventory.name, LiteInventory.model_spec, LiteInventory.remark), keyword
    )
    if keyword_condition is not None:
        query = query.where(keyword_condition)
    total = int((await session.scalar(select(func.count()).select_from(query.subquery()))) or 0)
    result = await session.scalars(
        query.order_by(LiteInventory.id).offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        LiteInventoryRead(
            id=item.id,
            name=item.name,
            model_spec=item.model_spec,
            unit_name=item.unit_name,
            quantity=item.quantity,
            remark=item.remark,
        )
        for item in result.all()
    ]
    return items, total
