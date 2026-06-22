from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_id

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.user import User


class Conversation(Base):
    __tablename__ = "conversations"
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

    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="conversations",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
