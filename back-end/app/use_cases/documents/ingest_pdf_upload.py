from dataclasses import dataclass

from typing import Protocol

class PdfUpload(Protocol):
    filename: str | None
    async def read(self, size: int = -1) -> bytes: ...
    async def seek(self, offset: int) -> None: ...
    async def close(self) -> None: ...

from app.models import Document, DocumentSourceType
from app.rag.ingestion import DocumentIngestor, IngestDocumentResult
from app.repositories import DocumentRepository, UnitOfWork
from app.services import DocumentStorage




@dataclass(frozen=True)
class PdfUploadIngestUseCase:
    repository: DocumentRepository
    unit_of_work: UnitOfWork
    document_storage: DocumentStorage
    document_ingestor: DocumentIngestor

    async def execute(self, upload: PdfUpload, title: str, uploader_id: str) -> IngestDocumentResult:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Informe o titulo do PDF.")
        file_name = (upload.filename or "").strip()
        if not file_name:
            raise ValueError("O arquivo PDF precisa possuir um nome.")
        document = Document.start_ingestion(
            source_url=None,
            title=normalized_title[:255],
            uploaded_by=uploader_id,
            source_type=DocumentSourceType.PDF,
            file_name=file_name[:255],
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
