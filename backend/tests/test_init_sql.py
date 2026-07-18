from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import Enum
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

import app.models  # noqa: F401
from app.core.database import Base

INIT_SQL = Path(__file__).parents[2] / "database" / "init.sql"
CREATE_TABLE = re.compile(
    r"CREATE TABLE IF NOT EXISTS `([^`]+)` \((.*?)\) ENGINE=",
    re.DOTALL,
)


def _table_blocks() -> dict[str, str]:
    return dict(CREATE_TABLE.findall(INIT_SQL.read_text(encoding="utf-8")))


def _column_definition(block: str, column: str) -> str:
    match = re.search(
        rf"^  `{re.escape(column)}` (.*?)(?=,\n  (?:`|CONSTRAINT|INDEX)|\Z)",
        block,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"init.sql 中缺少列定义：{column}"
    return match.group(1)


def test_init_sql_matches_current_model_schema() -> None:
    blocks = _table_blocks()
    model_tables = {table.name: table for table in Base.metadata.sorted_tables}

    assert set(blocks) == set(model_tables)

    for table_name, table in model_tables.items():
        block = blocks[table_name]
        sql_columns = set(re.findall(r"^  `([^`]+)`", block, re.MULTILINE))
        assert sql_columns == set(table.columns.keys()), f"{table_name} 的列与 ORM 不一致"

        sql_constraint_names = set(re.findall(r"CONSTRAINT `([^`]+)`", block))
        model_ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
        model_constraint_names = set(re.findall(r"CONSTRAINT `?([^`\s]+)`?", model_ddl))
        assert sql_constraint_names == model_constraint_names, (
            f"{table_name} 的约束与 ORM 不一致"
        )

        sql_index_names = set(re.findall(r"^  INDEX `([^`]+)`", block, re.MULTILINE))
        model_index_names = {index.name for index in table.indexes}
        assert sql_index_names == model_index_names, f"{table_name} 的索引与 ORM 不一致"

        for column in table.columns:
            definition = _column_definition(block, column.name)
            assert ("NOT NULL" in definition) is (not column.nullable), (
                f"{table_name}.{column.name} 的 NULL 约束与 ORM 不一致"
            )
            if isinstance(column.type, Enum):
                sql_values = re.findall(r"'([^']+)'", definition)
                assert sql_values == list(column.type.enums), (
                    f"{table_name}.{column.name} 的 ENUM 值与 ORM 不一致"
                )

        sql_foreign_keys = {
            (column, target_table, target_column, (on_delete or "").upper() or None)
            for column, target_table, target_column, on_delete in re.findall(
                r"FOREIGN KEY \(`([^`]+)`\) REFERENCES `([^`]+)` \(`([^`]+)`\)"
                r"(?: ON DELETE ([A-Z]+))?",
                block,
            )
        }
        model_foreign_keys = {
            (
                fk.parent.name,
                fk.column.table.name,
                fk.column.name,
                (fk.ondelete or "").upper() or None,
            )
            for fk in table.foreign_keys
        }
        assert sql_foreign_keys == model_foreign_keys, f"{table_name} 的外键与 ORM 不一致"


def test_init_sql_seeds_required_accounts_and_units() -> None:
    sql = INIT_SQL.read_text(encoding="utf-8")

    for username in ("admin", "warehouse", "purchase", "readonly"):
        assert f"('{username}', '$argon2id$" in sql
    for code, decimal_places in (("PCS", 0), ("SET", 0), ("M", 1), ("KG", 1)):
        assert re.search(rf"\('{code}', '[^']+', {decimal_places}, 1,", sql)
    assert "('PCS', '个', 0, 1," in sql
