from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_id

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.user import User


class Conversation(Base):
    __tablename__ = "conversations"
    channel: Mapped[str] = mapped_column(String(10), nullable=False, default="text", server_default="text")
    __table_args__ = (
        CheckConstraint(
            "user_id IS NOT NULL OR anonymous_id IS NOT NULL",
            name="conversation_owner_required",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(9),
        primary_key=True,
        default=generate_id,
    )

    user_id: Mapped[str | None] = mapped_column(
        String(9),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    anonymous_id: Mapped[str | None] = mapped_column(
        String(9),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(UTC) + timedelta(days=7), index=True,
    )

    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="conversations",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    @classmethod
    def start(cls, anonymous_id: str, first_message: str) -> "Conversation":
        return cls(
            anonymous_id=anonymous_id,
            title=cls._build_title(first_message),
        )

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    @staticmethod
    def _build_title(content: str) -> str:
        title = " ".join(content.split())

        if len(title) <= 48:
            return title

        return f"{title[:48].rstrip()}..."
