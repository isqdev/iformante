from dataclasses import dataclass
from pathlib import Path

from app.models import Document, DocumentSourceType
from app.rag.ingestion import DocumentIngestor, IngestDocumentResult
from app.repositories import DocumentRepository, UnitOfWork
from app.services import DocumentStorage, WebPageExtractor

HARDCODED_DOCUMENT_UPLOADER_ID = "isaque123"


@dataclass(frozen=True)
class WebPageIngestUseCase:
    repository: DocumentRepository
    unit_of_work: UnitOfWork
    document_storage: DocumentStorage
    document_ingestor: DocumentIngestor
    web_page_extractor: WebPageExtractor

    async def execute(self, source_url: str) -> IngestDocumentResult:
        extracted = await self.web_page_extractor.extract(source_url.strip())
        document = Document.start_ingestion(
            source_url=source_url.strip(),
            title=extracted.title,
            uploaded_by=HARDCODED_DOCUMENT_UPLOADER_ID,
            source_type=DocumentSourceType.WEB_PAGE,
        )
        await self.repository.create(document)
        await self.unit_of_work.commit()
        storage_path = Path(self.document_storage.document_dir(document.id)) / "indexed.md"
        try:
            result = await self.document_ingestor.execute_markdown(
                extracted.markdown,
                document_id=document.id,
                filename=extracted.title,
                storage_path=storage_path,
            )
        except Exception:
            document.mark_as_error()
            await self.unit_of_work.commit()
            raise
        document.mark_as_indexed(result.filename, result.storage_url, result.chunks_indexed)
        await self.unit_of_work.commit()
        return result
