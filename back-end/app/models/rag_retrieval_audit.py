from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_id


class RagRetrievalAudit(Base):
    __tablename__ = "rag_retrieval_audits"

    id: Mapped[str] = mapped_column(
        String(9),
        primary_key=True,
        default=generate_id,
    )
    message_id: Mapped[str] = mapped_column(
        String(9),
        ForeignKey("messages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    rewritten_query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_children: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    retrieved_parents: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
