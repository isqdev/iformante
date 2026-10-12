from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.models.base import Base, generate_id

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.document import Document


class UserRole(str, Enum):
    COMMON = "COMMON"
    ADMIN = "ADMIN"
    SUPER = "SUPER"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(9),
        primary_key=True,
        default=generate_id,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.COMMON.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="uploaded_by_user",
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
    )
