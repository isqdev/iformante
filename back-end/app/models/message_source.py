from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_id

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.message import Message


class MessageSource(Base):
    __tablename__ = "message_sources"

    id: Mapped[str] = mapped_column(String(9), primary_key=True, default=generate_id)
    message_id: Mapped[str] = mapped_column(String(9), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(
        String(9),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[str | None] = mapped_column(String(9), nullable=True)
    bbox: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    message: Mapped["Message"] = relationship("Message", back_populates="sources")
    document: Mapped["Document"] = relationship("Document")
