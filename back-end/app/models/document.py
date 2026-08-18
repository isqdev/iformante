from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.models.base import Base, generate_id

if TYPE_CHECKING:
    from app.models.rag import RagDocumentParent
    from app.models.user import User


class IngestionStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    INDEXED = "INDEXED"
    ERROR = "ERROR"


class DocumentSourceType(str, Enum):
    PDF = "PDF"
    WEB_PAGE = "WEB_PAGE"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(9),
        primary_key=True,
        default=generate_id,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentSourceType.PDF.value,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    stored_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    ingestion_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=IngestionStatus.PENDING.value,
    )

    total_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    uploaded_by: Mapped[str] = mapped_column(
        String(9),
        ForeignKey("users.id", ondelete="RESTRICT"),
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

    uploaded_by_user: Mapped["User"] = relationship(
        "User",
        back_populates="documents",
    )
    rag_parents: Mapped[list["RagDocumentParent"]] = relationship(
        "RagDocumentParent", back_populates="document", cascade="all, delete-orphan"
    )

    @classmethod
    def start_ingestion(
        cls,
        source_url: str | None,
        title: str,
        uploaded_by: str,
        source_type: DocumentSourceType = DocumentSourceType.PDF,
    ) -> "Document":
        return cls(
            title=title,
            source_url=source_url,
            source_type=source_type.value,
            file_name="",
            stored_path="",
            ingestion_status=IngestionStatus.PROCESSING.value,
            total_chunks=0,
            uploaded_by=uploaded_by,
        )

    def mark_as_indexed(
        self,
        file_name: str,
        stored_path: str,
        total_chunks: int,
    ) -> None:
        if total_chunks <= 0:
            raise ValueError("Um documento indexado precisa possuir chunks.")

        self.file_name = file_name
        self.stored_path = stored_path
        self.total_chunks = total_chunks
        self.ingestion_status = IngestionStatus.INDEXED.value

    def mark_as_error(self) -> None:
        self.ingestion_status = IngestionStatus.ERROR.value
