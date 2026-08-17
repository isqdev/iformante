"""create message sources

Revision ID: 202607220001
Revises: 202606220001
Create Date: 2026-07-22 00:01:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202607220001"
down_revision: str | None = "202606220001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_sources",
        sa.Column("id", sa.String(length=9), nullable=False),
        sa.Column("message_id", sa.String(length=9), nullable=False),
        sa.Column("document_id", sa.String(length=9), nullable=False),
        sa.Column("chunk_id", sa.String(length=9), nullable=True),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rank > 0", name=op.f("ck_message_sources_rank_positive")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_message_sources_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_sources_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_sources")),
        sa.UniqueConstraint(
            "message_id",
            "rank",
            name=op.f("uq_message_sources_message_id_rank"),
        ),
    )
    op.create_index(
        op.f("ix_message_sources_document_id"),
        "message_sources",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_message_sources_message_id"),
        "message_sources",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_message_sources_message_id"), table_name="message_sources")
    op.drop_index(op.f("ix_message_sources_document_id"), table_name="message_sources")
    op.drop_table("message_sources")
