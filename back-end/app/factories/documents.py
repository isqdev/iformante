from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.use_cases.documents import (
    DeleteDocumentUseCase,
    DocumentManager,
    IngestDocumentUseCase,
)


def get_document_manager(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> DocumentManager:
    return DocumentManager(session)


def get_ingest_document_use_case() -> IngestDocumentUseCase:
    return IngestDocumentUseCase(
        openai_api_key=settings.openai_api_key,
        qdrant_url=settings.qdrant_url,
        qdrant_api_key=settings.qdrant_api_key,
        qdrant_collection=settings.qdrant_collection,
        embedding_model=settings.openai_embedding_model,
        embedding_dimensions=settings.openai_embedding_dimensions,
        cloudinary_cloud_name=settings.cloudinary_cloud_name,
        cloudinary_api_key=settings.cloudinary_api_key,
        cloudinary_api_secret=settings.cloudinary_api_secret,
    )


def get_delete_document_use_case(
    document_manager: Annotated[DocumentManager, Depends(get_document_manager)],
) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(
        qdrant_url=settings.qdrant_url,
        qdrant_collection=settings.qdrant_collection,
        document_manager=document_manager,
        cloudinary_cloud_name=settings.cloudinary_cloud_name,
        cloudinary_api_key=settings.cloudinary_api_key,
        cloudinary_api_secret=settings.cloudinary_api_secret,
    )
