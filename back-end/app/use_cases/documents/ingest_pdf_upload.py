from dataclasses import dataclass

from fastapi import UploadFile

from app.models import Document, DocumentSourceType
from app.rag.ingestion import DocumentIngestor, IngestDocumentResult
from app.repositories import DocumentRepository, UnitOfWork
from app.services import DocumentStorage

HARDCODED_DOCUMENT_UPLOADER_ID = "isaque123"


@dataclass(frozen=True)
class PdfUploadIngestUseCase:
    repository: DocumentRepository
    unit_of_work: UnitOfWork
    document_storage: DocumentStorage
    document_ingestor: DocumentIngestor

    async def execute(self, upload: UploadFile, title: str) -> IngestDocumentResult:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Informe o titulo do PDF.")
        document = Document.start_ingestion(
            source_url=None,
            title=normalized_title[:255],
            uploaded_by=HARDCODED_DOCUMENT_UPLOADER_ID,
            source_type=DocumentSourceType.PDF,
        )
        await self.repository.create(document)
        await self.unit_of_work.commit()
        try:
            uploaded = await self.document_storage.save_pdf_upload(upload, document.id)
            result = await self.document_ingestor.execute(
                uploaded.path,
                document_id=document.id,
                filename=uploaded.filename,
            )
        except Exception:
            document.mark_as_error()
            await self.unit_of_work.commit()
            raise
        document.mark_as_indexed(result.filename, result.storage_url, result.chunks_indexed)
        await self.unit_of_work.commit()
        return result
