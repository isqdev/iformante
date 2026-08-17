from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_database_session
from pathlib import Path

from app.config import settings
from app.rag.ingestion import DocumentIngestor
from app.repositories import DocumentRepository, RagRepository, UnitOfWork
from app.services import DocumentStorage
from app.use_cases.documents import (
    DeleteDocumentUseCase,
    IngestDocumentUseCase,
    ListDocumentsUseCase,
)

def get_list_documents_use_case(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ListDocumentsUseCase:
    return ListDocumentsUseCase(DocumentRepository(session))


def get_ingest_document_use_case(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> IngestDocumentUseCase:
    storage = DocumentStorage(Path(settings.document_storage_dir))
    return IngestDocumentUseCase(
        repository=DocumentRepository(session),
        unit_of_work=UnitOfWork(session),
        document_storage=storage,
        document_ingestor=DocumentIngestor(
            settings.openai_api_key,
            settings.openai_embedding_model,
            storage,
            RagRepository(session),
        ),
    )


def get_delete_document_use_case(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(DocumentRepository(session), UnitOfWork(session), Path(settings.document_storage_dir))
