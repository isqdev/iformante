"""cascade message sources when a document is deleted

Revision ID: 202607280001
Revises: 202607230001
Create Date: 2026-07-28 00:01:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "202607280001"
down_revision: str | None = "202607230001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("fk_message_sources_document_id_documents"),
        "message_sources",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_message_sources_document_id_documents"),
        "message_sources",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_message_sources_document_id_documents"),
        "message_sources",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_message_sources_document_id_documents"),
        "message_sources",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="RESTRICT",
    )
