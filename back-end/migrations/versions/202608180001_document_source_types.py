"""add document source type

Revision ID: 202608180001
Revises: 202607280001
Create Date: 2026-08-18 00:00:01.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202608180001"
down_revision: str | None = "202607280001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "source_type",
            sa.String(length=20),
            nullable=False,
            server_default="PDF",
        ),
    )
    op.alter_column("documents", "source_url", existing_type=sa.String(length=2048), nullable=True)
    op.alter_column("documents", "source_type", server_default=None)


def downgrade() -> None:
    op.execute("UPDATE documents SET source_url = '' WHERE source_url IS NULL")
    op.alter_column("documents", "source_url", existing_type=sa.String(length=2048), nullable=False)
    op.drop_column("documents", "source_type")
