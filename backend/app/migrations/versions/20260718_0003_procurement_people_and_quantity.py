"""add procurement people and standardize quantity precision

Revision ID: 20260718_0003
Revises: 20260717_0002
Create Date: 2026-07-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import BIGINT

revision = "20260718_0003"
down_revision = "20260717_0002"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    columns = {column["name"] for column in _inspector().get_columns("purchase_material")}
    if "actual_demand_person" not in columns:
        op.add_column(
            "purchase_material",
            sa.Column("actual_demand_person", sa.String(length=128), nullable=True),
        )
    if "purchase_responsible_id" not in columns:
        op.add_column(
            "purchase_material",
            sa.Column("purchase_responsible_id", BIGINT(unsigned=True), nullable=True),
        )
    op.execute(
        "UPDATE purchase_material pm "
        "LEFT JOIN user u ON u.id = pm.created_by "
        "SET pm.actual_demand_person = COALESCE(u.display_name, '待补充'), "
        "pm.purchase_responsible_id = COALESCE(pm.created_by, 1)"
    )
    op.alter_column(
        "purchase_material", "actual_demand_person", existing_type=sa.String(128), nullable=False
    )
    op.alter_column(
        "purchase_material",
        "purchase_responsible_id",
        existing_type=BIGINT(unsigned=True),
        nullable=False,
    )
    foreign_keys = {item.get("name") for item in _inspector().get_foreign_keys("purchase_material")}
    if "fk_purchase_material_purchase_responsible_id_user" not in foreign_keys:
        op.create_foreign_key(
            "fk_purchase_material_purchase_responsible_id_user",
            "purchase_material",
            "user",
            ["purchase_responsible_id"],
            ["id"],
        )
    indexes = {item.get("name") for item in _inspector().get_indexes("purchase_material")}
    if "ix_purchase_material_purchase_responsible_id" not in indexes:
        op.create_index(
            "ix_purchase_material_purchase_responsible_id",
            "purchase_material",
            ["purchase_responsible_id"],
        )
    op.execute("UPDATE measurement_unit SET decimal_places = LEAST(decimal_places, 1)")
    checks = {item.get("name") for item in _inspector().get_check_constraints("measurement_unit")}
    if "ck_measurement_unit_decimal_places_range" in checks:
        op.drop_constraint(
            "ck_measurement_unit_decimal_places_range", "measurement_unit", type_="check"
        )
    op.create_check_constraint(
        "ck_measurement_unit_decimal_places_range",
        "measurement_unit",
        "decimal_places >= 0 AND decimal_places <= 1",
    )
    quantity_columns = {
        "stock_balance": ["quantity"],
        "stock_replenishment_policy": ["minimum_qty", "target_qty"],
        "purchase_request_line": ["requested_qty", "received_qty"],
        "stock_operation_line": ["quantity", "before_qty", "after_qty"],
    }
    defaulted_columns = {("stock_balance", "quantity"), ("purchase_request_line", "received_qty")}
    for table, columns in quantity_columns.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                existing_type=sa.Numeric(18, 3),
                type_=sa.Numeric(18, 1),
                existing_nullable=False,
                existing_server_default="0" if (table, column) in defaulted_columns else False,
            )


def downgrade() -> None:
    quantity_columns = {
        "stock_balance": ["quantity"],
        "stock_replenishment_policy": ["minimum_qty", "target_qty"],
        "purchase_request_line": ["requested_qty", "received_qty"],
        "stock_operation_line": ["quantity", "before_qty", "after_qty"],
    }
    defaulted_columns = {("stock_balance", "quantity"), ("purchase_request_line", "received_qty")}
    for table, columns in quantity_columns.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                existing_type=sa.Numeric(18, 1),
                type_=sa.Numeric(18, 3),
                existing_nullable=False,
                existing_server_default="0" if (table, column) in defaulted_columns else False,
            )
    op.drop_constraint(
        "ck_measurement_unit_decimal_places_range", "measurement_unit", type_="check"
    )
    op.create_check_constraint(
        "ck_measurement_unit_decimal_places_range",
        "measurement_unit",
        "decimal_places >= 0 AND decimal_places <= 3",
    )
    op.drop_index("ix_purchase_material_purchase_responsible_id", table_name="purchase_material")
    op.drop_constraint(
        "fk_purchase_material_purchase_responsible_id_user", "purchase_material", type_="foreignkey"
    )
    op.drop_column("purchase_material", "purchase_responsible_id")
    op.drop_column("purchase_material", "actual_demand_person")
