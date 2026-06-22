"""change anonymous_id to varchar(9)

Revision ID: 202606220001
Revises: 202606070001
Create Date: 2026-06-22 00:01:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202606220001"
down_revision: str | None = "202606070001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "conversations",
        "anonymous_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=9),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "conversations",
        "anonymous_id",
        existing_type=sa.String(length=9),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
