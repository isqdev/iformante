"""enforce unique document sources

Revision ID: 202608190001
Revises: 202608180001
Create Date: 2026-08-19 00:00:01.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "202608190001"
down_revision: str | None = "202608180001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_documents_file_name", "documents", ["file_name"])
    op.create_unique_constraint("uq_documents_source_url", "documents", ["source_url"])


def downgrade() -> None:
    op.drop_constraint("uq_documents_source_url", "documents", type_="unique")
    op.drop_constraint("uq_documents_file_name", "documents", type_="unique")
