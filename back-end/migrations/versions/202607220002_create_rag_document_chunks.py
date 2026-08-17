"""create rag document chunks

Revision ID: 202607220002
Revises: 202607220001
Create Date: 2026-07-22 00:02:00.000000
"""
from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202607220002"
down_revision: str | None = "202607220001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "rag_document_parents",
        sa.Column("id", sa.String(length=9), nullable=False),
        sa.Column("document_id", sa.String(length=9), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name=op.f("ck_rag_document_parents_chunk_index_non_negative"),
        ),
        sa.CheckConstraint(
            "token_count IS NULL OR token_count > 0",
            name=op.f("ck_rag_document_parents_token_count_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_rag_document_parents_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rag_document_parents")),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name=op.f("uq_rag_document_parents_document_id_chunk_index"),
        ),
    )
    op.create_index(
        op.f("ix_rag_document_parents_document_id"),
        "rag_document_parents",
        ["document_id"],
        unique=False,
    )

    op.create_table(
        "rag_document_children",
        sa.Column("id", sa.String(length=9), nullable=False),
        sa.Column("parent_id", sa.String(length=9), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column(
            "content_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('portuguese', content)", persisted=True),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("chunk_index >= 0", name=op.f("ck_rag_document_children_chunk_index_non_negative")),
        sa.CheckConstraint("token_count IS NULL OR token_count > 0", name=op.f("ck_rag_document_children_token_count_positive")),
        sa.ForeignKeyConstraint(["parent_id"], ["rag_document_parents.id"], name=op.f("fk_rag_document_children_parent_id_rag_document_parents"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rag_document_children")),
        sa.UniqueConstraint("parent_id", "chunk_index", name=op.f("uq_rag_document_children_parent_id_chunk_index")),
    )
    op.create_index(
        "ix_rag_document_children_embedding_hnsw",
        "rag_document_children",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        op.f("ix_rag_document_children_parent_id"),
        "rag_document_children",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_rag_document_children_content_tsv",
        "rag_document_children",
        ["content_tsv"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_rag_document_children_content_tsv", table_name="rag_document_children")
    op.drop_index(op.f("ix_rag_document_children_parent_id"), table_name="rag_document_children")
    op.drop_index("ix_rag_document_children_embedding_hnsw", table_name="rag_document_children")
    op.drop_table("rag_document_children")

    op.drop_index(op.f("ix_rag_document_parents_document_id"), table_name="rag_document_parents")
    op.drop_table("rag_document_parents")
