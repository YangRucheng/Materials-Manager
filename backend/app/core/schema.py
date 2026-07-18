from __future__ import annotations

from typing import Any

from sqlalchemy import Enum, inspect
from sqlalchemy.engine import Connection

import app.models  # noqa: F401
from app.core.database import Base


def schema_differences(connection: Connection) -> dict[str, Any]:
    """Read the database catalog and report drift without changing the schema."""
    inspector = inspect(connection)
    expected_tables = {table.name: table for table in Base.metadata.sorted_tables}
    actual_tables = set(inspector.get_table_names())
    differences: dict[str, Any] = {}

    missing_tables = sorted(set(expected_tables) - actual_tables)
    unexpected_tables = sorted(actual_tables - set(expected_tables))
    if missing_tables:
        differences["missing_tables"] = missing_tables
    if unexpected_tables:
        differences["unexpected_tables"] = unexpected_tables

    column_differences: dict[str, Any] = {}
    for table_name in sorted(set(expected_tables) & actual_tables):
        expected_columns = expected_tables[table_name].columns
        actual_columns = {
            column["name"]: column for column in inspector.get_columns(table_name)
        }
        table_difference: dict[str, Any] = {}

        missing_columns = sorted(set(expected_columns.keys()) - set(actual_columns))
        unexpected_columns = sorted(set(actual_columns) - set(expected_columns.keys()))
        if missing_columns:
            table_difference["missing_columns"] = missing_columns
        if unexpected_columns:
            table_difference["unexpected_columns"] = unexpected_columns

        incompatible_columns: list[str] = []
        for column_name in set(expected_columns.keys()) & set(actual_columns):
            expected = expected_columns[column_name]
            actual = actual_columns[column_name]
            if bool(actual["nullable"]) != expected.nullable:
                incompatible_columns.append(column_name)
                continue
            if isinstance(expected.type, Enum):
                actual_values = getattr(actual["type"], "enums", None)
                if actual_values is not None and list(actual_values) != list(expected.type.enums):
                    incompatible_columns.append(column_name)
        if incompatible_columns:
            table_difference["incompatible_columns"] = sorted(incompatible_columns)
        if table_difference:
            column_differences[table_name] = table_difference

    if column_differences:
        differences["columns"] = column_differences
    return differences
