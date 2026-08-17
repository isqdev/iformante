"""create rag retrieval audits

Revision ID: 202607230001
Revises: 202607220002
Create Date: 2026-07-23 00:01:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202607230001"
down_revision: str | None = "202607220002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rag_retrieval_audits",
        sa.Column("id", sa.String(length=9), nullable=False),
        sa.Column("message_id", sa.String(length=9), nullable=False),
        sa.Column("rewritten_query", sa.Text(), nullable=False),
        sa.Column(
            "retrieved_children",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "retrieved_parents",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_rag_retrieval_audits_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_rag_retrieval_audits"),
        ),
        sa.UniqueConstraint(
            "message_id",
            name=op.f("uq_rag_retrieval_audits_message_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("rag_retrieval_audits")
