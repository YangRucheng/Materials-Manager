from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


def apply_schema_migrations(connection: Connection) -> list[str]:
    """Apply small, idempotent schema upgrades required before ORM queries run."""
    inspector = inspect(connection)
    if "purchase_material" not in inspector.get_table_names():
        return []

    applied: list[str] = []
    column_names = {column["name"] for column in inspector.get_columns("purchase_material")}
    index_names = {index["name"] for index in inspector.get_indexes("purchase_material")}
    dialect = connection.dialect.name

    if "status" not in column_names:
        if dialect == "mysql":
            connection.execute(
                text(
                    "ALTER TABLE `purchase_material` "
                    "ADD COLUMN `status` ENUM('NORMAL', 'ARCHIVED') "
                    "NOT NULL DEFAULT 'NORMAL' AFTER `identity_hash`"
                )
            )
        else:
            connection.execute(
                text(
                    "ALTER TABLE purchase_material "
                    "ADD COLUMN status VARCHAR(8) NOT NULL DEFAULT 'NORMAL'"
                )
            )
        applied.append("purchase_material.status")

    if "ix_purchase_material_status" not in index_names:
        if dialect == "mysql":
            connection.execute(
                text(
                    "ALTER TABLE `purchase_material` "
                    "ADD INDEX `ix_purchase_material_status` (`status`)"
                )
            )
        else:
            connection.execute(
                text("CREATE INDEX ix_purchase_material_status ON purchase_material (status)")
            )
        applied.append("ix_purchase_material_status")

    return applied
