"""initial schema

Revision ID: 20260717_0001
Revises:
Create Date: 2026-07-17
"""

from alembic import op

import app.models  # noqa: F401
from app.core.database import Base

revision = "20260717_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
