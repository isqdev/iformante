from pathlib import Path
from urllib.parse import unquote, urlparse

from app.models import Document, DocumentSourceType
from app.rag.ingestion import DocumentIngestor, IngestDocumentResult
from app.repositories import DocumentRepository, UnitOfWork
from app.services import DocumentStorage

HARDCODED_DOCUMENT_UPLOADER_ID = "isaque123"


class IngestDocumentUseCase:
    def __init__(
        self,
        repository: DocumentRepository,
        unit_of_work: UnitOfWork,
        document_storage: DocumentStorage,
        document_ingestor: DocumentIngestor,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._document_storage = document_storage
        self._document_ingestor = document_ingestor

    async def execute(self, source_url: str) -> IngestDocumentResult:
        document = Document.start_ingestion(
            source_url=source_url,
            title=self._build_title(source_url),
            uploaded_by=HARDCODED_DOCUMENT_UPLOADER_ID,
            source_type=DocumentSourceType.PDF,
        )
        await self._repository.create(document)
        await self._unit_of_work.commit()

        try:
            downloaded = await self._document_storage.download_pdf(
                source_url,
                document.id,
            )
            result = await self._document_ingestor.execute(
                downloaded.path,
                document_id=document.id,
                filename=downloaded.filename,
            )
        except Exception:
            document.mark_as_error()
            await self._unit_of_work.commit()
            raise

        document.mark_as_indexed(
            file_name=result.filename,
            stored_path=result.storage_url,
            total_chunks=result.chunks_indexed,
        )
        await self._unit_of_work.commit()
        return result

    def _build_title(self, source_url: str) -> str:
        parsed_url = urlparse(source_url)
        filename = Path(unquote(parsed_url.path)).name
        return (filename or source_url)[:255]
