"""simplify procurement planning and allow negative balances

Revision ID: 20260717_0002
Revises: 20260717_0001
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260717_0002"
down_revision = "20260717_0001"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _drop_unique_for_columns(table: str, columns: list[str]) -> None:
    inspector = _inspector()
    for constraint in inspector.get_unique_constraints(table):
        if constraint.get("column_names") == columns and constraint.get("name"):
            op.drop_constraint(constraint["name"], table, type_="unique")
            return
    for index in inspector.get_indexes(table):
        if (
            index.get("unique")
            and index.get("column_names") == columns
            and index.get("name")
        ):
            op.drop_index(index["name"], table_name=table)
            return


def _ensure_index(table: str, name: str, columns: list[str]) -> None:
    if name not in {index["name"] for index in _inspector().get_indexes(table)}:
        op.create_index(name, table, columns, unique=False)


def _drop_check(table: str, check_name: str) -> None:
    checks = {item.get("name") for item in _inspector().get_check_constraints(table)}
    if check_name in checks:
        op.drop_constraint(check_name, table, type_="check")


def upgrade() -> None:
    if _has_table("material_code_application_image"):
        op.drop_table("material_code_application_image")
    if _has_table("material_code_application"):
        op.drop_table("material_code_application")

    _drop_unique_for_columns("purchase_material", ["material_code"])
    # MySQL 的外键可能复用唯一索引，先补普通索引再删除唯一约束。
    _ensure_index(
        "purchase_material", "ix_purchase_material_stock_material_id", ["stock_material_id"]
    )
    _drop_unique_for_columns("purchase_material", ["stock_material_id"])
    _ensure_index(
        "purchase_material", "ix_purchase_material_stock_material_id", ["stock_material_id"]
    )
    _ensure_index("purchase_material", "ix_purchase_material_material_code", ["material_code"])

    _drop_unique_for_columns("purchase_request", ["request_no"])
    _ensure_index("purchase_request", "ix_purchase_request_request_no", ["request_no"])
    request_columns = {
        column["name"]: column
        for column in _inspector().get_columns("purchase_request")
    }
    if request_columns["request_no"]["type"].length != 128:
        op.alter_column(
            "purchase_request",
            "request_no",
            existing_type=sa.String(length=request_columns["request_no"]["type"].length),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
    if "external_request_no" in request_columns:
        indexes = {index["name"] for index in _inspector().get_indexes("purchase_request")}
        if "ix_purchase_request_external_request_no" in indexes:
            op.drop_index("ix_purchase_request_external_request_no", table_name="purchase_request")
        op.drop_column("purchase_request", "external_request_no")

    _drop_check("stock_balance", "ck_stock_balance_quantity_nonnegative")
    _drop_check("purchase_request_line", "ck_purchase_request_line_received_range")
    checks = {
        item.get("name") for item in _inspector().get_check_constraints("purchase_request_line")
    }
    if "ck_purchase_request_line_received_nonnegative" not in checks:
        op.create_check_constraint(
            "ck_purchase_request_line_received_nonnegative",
            "purchase_request_line",
            "received_qty >= 0",
        )


def downgrade() -> None:
    raise NotImplementedError("该迁移删除了旧编码申请数据，不支持自动降级")
