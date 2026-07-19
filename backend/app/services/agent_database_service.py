from __future__ import annotations

import base64
import logging
import re
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.schemas import AgentDatabaseExecuteRead, AgentDatabaseExecuteRequest

logger = logging.getLogger("spare_parts.agent_database")
ALLOWED_STATEMENTS = {"SELECT", "INSERT", "UPDATE", "DELETE", "ALTER"}
BLOCKED_SELECT_FEATURES = re.compile(
    r"\b(?:INTO\s+(?:OUTFILE|DUMPFILE)|LOAD_FILE\s*\()",
    re.IGNORECASE,
)


def _invalid_sql(message: str) -> AppError:
    return AppError("AGENT_DATABASE_SQL_FORBIDDEN", message, status_code=400)


def validate_sql(sql: str) -> str:
    statement = sql.strip()
    masked: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(statement):
        char = statement[index]
        if quote is not None:
            masked.append(" ")
            if char == "\\" and index + 1 < len(statement):
                masked.append(" ")
                index += 2
                continue
            if char == quote:
                if index + 1 < len(statement) and statement[index + 1] == quote:
                    masked.append(" ")
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            masked.append(" ")
            index += 1
            continue
        if char == ";":
            raise _invalid_sql("每次只能执行一条 SQL，不能包含分号")
        if char == "#" or statement.startswith("--", index) or statement.startswith("/*", index):
            raise _invalid_sql("SQL 不允许包含注释")
        masked.append(char)
        index += 1

    match = re.match(r"^([A-Za-z]+)\b", statement)
    statement_type = match.group(1).upper() if match else ""
    if statement_type not in ALLOWED_STATEMENTS:
        raise _invalid_sql("只允许执行 SELECT、INSERT、UPDATE、DELETE、ALTER TABLE")
    if statement_type == "ALTER" and not re.match(
        r"^ALTER\s+TABLE\s+[`A-Za-z0-9_.]+\s+", statement, re.IGNORECASE
    ):
        raise _invalid_sql("ALTER 仅允许修改数据表结构")
    if BLOCKED_SELECT_FEATURES.search("".join(masked)):
        raise _invalid_sql("不允许通过 SQL 读写数据库服务器文件")
    return statement_type


def _json_value(value: Any) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"base64:{base64.b64encode(value).decode('ascii')}"
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)


async def execute_sql(
    session: AsyncSession,
    data: AgentDatabaseExecuteRequest,
    username: str,
) -> AgentDatabaseExecuteRead:
    statement_type = validate_sql(data.sql)
    result: Any = await session.execute(text(data.sql), data.parameters)
    columns: list[str] = []
    rows: list[dict[str, object]] = []
    truncated = False
    if result.returns_rows:
        columns = list(result.keys())
        fetched = list(result.mappings().fetchmany(data.max_rows + 1))
        truncated = len(fetched) > data.max_rows
        rows = [
            {str(key): _json_value(value) for key, value in row.items()}
            for row in fetched[: data.max_rows]
        ]
    row_count = len(rows)
    raw_rowcount = getattr(result, "rowcount", -1)
    affected_rows = raw_rowcount if isinstance(raw_rowcount, int) and raw_rowcount >= 0 else None
    raw_last_id = getattr(result, "lastrowid", None) if statement_type == "INSERT" else None
    last_insert_id = (
        _json_value(raw_last_id)
        if raw_last_id is not None and (not isinstance(raw_last_id, int) or raw_last_id >= 0)
        else None
    )
    digest = sha256(data.sql.encode("utf-8")).hexdigest()[:16]
    logger.info(
        "agent database statement user=%s type=%s affected_rows=%s returned_rows=%s sql_hash=%s",
        username,
        statement_type,
        affected_rows,
        row_count,
        digest,
    )
    return AgentDatabaseExecuteRead(
        statement_type=statement_type,
        columns=columns,
        rows=rows,
        row_count=row_count,
        affected_rows=affected_rows,
        last_insert_id=last_insert_id if isinstance(last_insert_id, (str, int)) else None,
        truncated=truncated,
    )


def _read_schema(connection: Connection) -> dict[str, object]:
    inspector = inspect(connection)
    tables: list[dict[str, object]] = []
    for table_name in sorted(inspector.get_table_names()):
        primary_key = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
        columns = [
            {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": bool(column["nullable"]),
                "default": _json_value(column.get("default")),
                "primary_key": column["name"] in primary_key,
            }
            for column in inspector.get_columns(table_name)
        ]
        foreign_keys = [
            {
                "columns": item.get("constrained_columns") or [],
                "referred_table": item.get("referred_table"),
                "referred_columns": item.get("referred_columns") or [],
            }
            for item in inspector.get_foreign_keys(table_name)
        ]
        tables.append(
            {
                "name": table_name,
                "columns": columns,
                "foreign_keys": foreign_keys,
            }
        )
    return {"tables": tables}


async def read_schema(session: AsyncSession) -> dict[str, object]:
    connection = await session.connection()
    return await connection.run_sync(_read_schema)
