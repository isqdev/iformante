from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_id

if TYPE_CHECKING:
    from app.models.document import Document


class RagDocumentParent(Base):
    __tablename__ = "rag_document_parents"

    id: Mapped[str] = mapped_column(String(9), primary_key=True, default=generate_id)
    document_id: Mapped[str] = mapped_column(String(9), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    bbox: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    document: Mapped["Document"] = relationship("Document", back_populates="rag_parents")
    children: Mapped[list["RagDocumentChild"]] = relationship("RagDocumentChild", back_populates="parent", cascade="all, delete-orphan")


class RagDocumentChild(Base):
    __tablename__ = "rag_document_children"

    id: Mapped[str] = mapped_column(String(9), primary_key=True, default=generate_id)
    parent_id: Mapped[str] = mapped_column(String(9), ForeignKey("rag_document_parents.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    content_tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('portuguese', content)", persisted=True),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    parent: Mapped["RagDocumentParent"] = relationship("RagDocumentParent", back_populates="children")
