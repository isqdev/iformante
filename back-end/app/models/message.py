from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_id

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message_source import MessageSource


class MessageAuthor(str, Enum):
    USER = "USER"
    AI = "AI"


class Message(Base):
    __tablename__ = "messages"
    response_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="text", server_default="text")
    playback_status: Mapped[str | None] = mapped_column(String(16), nullable=True)

    id: Mapped[str] = mapped_column(
        String(9),
        primary_key=True,
        default=generate_id,
    )

    conversation_id: Mapped[str] = mapped_column(
        String(9),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    author: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )
    sources: Mapped[list["MessageSource"]] = relationship(
        "MessageSource",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageSource.rank",
    )

    @classmethod
    def from_user(cls, conversation_id: str, content: str) -> "Message":
        return cls(
            conversation_id=conversation_id,
            author=MessageAuthor.USER.value,
            content=content,
        )

    @classmethod
    def from_assistant(cls, conversation_id: str, content: str) -> "Message":
        return cls(
            conversation_id=conversation_id,
            author=MessageAuthor.AI.value,
            content=content,
        )
