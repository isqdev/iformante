from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, IngestionStatus
from app.repository import DocumentRepository

HARDCODED_DOCUMENT_UPLOADER_ID = "isaque123"


class DocumentDomain:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._document_repository = DocumentRepository(session)

    async def create_processing_document(self, source_url: str) -> Document:
        document = Document(
            title=self._build_title(source_url),
            source_url=source_url,
            file_name="",
            stored_path="",
            ingestion_status=IngestionStatus.PROCESSING.value,
            total_chunks=0,
            uploaded_by=HARDCODED_DOCUMENT_UPLOADER_ID,
        )
        await self._document_repository.create(document)
        await self._session.commit()
        return document

    async def mark_document_indexed(
        self,
        document: Document,
        file_name: str,
        stored_path: Path,
        total_chunks: int,
    ) -> None:
        document.file_name = file_name
        document.stored_path = str(stored_path)
        document.total_chunks = total_chunks
        document.ingestion_status = IngestionStatus.INDEXED.value
        await self._session.commit()

    async def mark_document_error(self, document: Document) -> None:
        document.ingestion_status = IngestionStatus.ERROR.value
        await self._session.commit()

    def _build_title(self, source_url: str) -> str:
        parsed_url = urlparse(source_url)
        filename = Path(unquote(parsed_url.path)).name

        if filename:
            return filename[:255]

        return source_url[:255]
