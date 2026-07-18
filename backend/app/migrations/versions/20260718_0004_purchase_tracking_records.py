"""align purchase plans and flattened tracking records

Revision ID: 20260718_0004
Revises: 20260718_0003
Create Date: 2026-07-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import BIGINT

revision = "20260718_0004"
down_revision = "20260718_0003"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    purchase_columns = {
        column["name"] for column in _inspector().get_columns("purchase_material")
    }
    if "purchase_responsible" not in purchase_columns:
        op.add_column(
            "purchase_material",
            sa.Column("purchase_responsible", sa.String(length=128), nullable=True),
        )
    if "planned_qty" not in purchase_columns:
        op.add_column(
            "purchase_material",
            sa.Column("planned_qty", sa.Numeric(18, 1), nullable=True),
        )
    if "usage" not in purchase_columns:
        op.add_column(
            "purchase_material", sa.Column("usage", sa.String(length=500), nullable=True)
        )
    if "project_subitem_id" not in purchase_columns:
        op.add_column(
            "purchase_material",
            sa.Column("project_subitem_id", BIGINT(unsigned=True), nullable=True),
        )

    op.execute(
        "UPDATE purchase_material pm "
        "LEFT JOIN user u ON u.id = pm.purchase_responsible_id "
        "SET pm.purchase_responsible = COALESCE(u.display_name, '待补充'), "
        "pm.planned_qty = COALESCE((SELECT SUM(prl.requested_qty) "
        "FROM purchase_request_line prl WHERE prl.purchase_material_id = pm.id), 1), "
        "pm.usage = COALESCE((SELECT prl.usage FROM purchase_request_line prl "
        "WHERE prl.purchase_material_id = pm.id ORDER BY prl.id LIMIT 1), '待补充'), "
        "pm.project_subitem_id = (SELECT prl.project_subitem_id FROM purchase_request_line prl "
        "WHERE prl.purchase_material_id = pm.id ORDER BY prl.id LIMIT 1)"
    )

    foreign_keys = _inspector().get_foreign_keys("purchase_material")
    for foreign_key in foreign_keys:
        if foreign_key.get("constrained_columns") == ["purchase_responsible_id"]:
            op.drop_constraint(
                foreign_key["name"], "purchase_material", type_="foreignkey"
            )
            break
    indexes = {item.get("name") for item in _inspector().get_indexes("purchase_material")}
    if "ix_purchase_material_purchase_responsible_id" in indexes:
        op.drop_index(
            "ix_purchase_material_purchase_responsible_id", table_name="purchase_material"
        )
    if "purchase_responsible_id" in purchase_columns:
        op.drop_column("purchase_material", "purchase_responsible_id")

    op.alter_column(
        "purchase_material",
        "purchase_responsible",
        existing_type=sa.String(128),
        nullable=False,
    )
    op.alter_column(
        "purchase_material",
        "planned_qty",
        existing_type=sa.Numeric(18, 1),
        nullable=False,
    )
    op.alter_column(
        "purchase_material", "usage", existing_type=sa.String(500), nullable=False
    )
    indexes = {item.get("name") for item in _inspector().get_indexes("purchase_material")}
    if "ix_purchase_material_purchase_responsible" not in indexes:
        op.create_index(
            "ix_purchase_material_purchase_responsible",
            "purchase_material",
            ["purchase_responsible"],
        )
    if "ix_purchase_material_project_subitem_id" not in indexes:
        op.create_index(
            "ix_purchase_material_project_subitem_id",
            "purchase_material",
            ["project_subitem_id"],
        )
    foreign_key_names = {
        item.get("name") for item in _inspector().get_foreign_keys("purchase_material")
    }
    if "fk_purchase_material_project_subitem_id_project_subitem" not in foreign_key_names:
        op.create_foreign_key(
            "fk_purchase_material_project_subitem_id_project_subitem",
            "purchase_material",
            "project_subitem",
            ["project_subitem_id"],
            ["id"],
        )

    request_columns = {
        column["name"] for column in _inspector().get_columns("purchase_request")
    }
    if "salesperson" not in request_columns:
        op.add_column(
            "purchase_request", sa.Column("salesperson", sa.String(length=128), nullable=True)
        )


def downgrade() -> None:
    raise NotImplementedError("该迁移改变了申购负责人和计划数据语义，不支持自动降级")
