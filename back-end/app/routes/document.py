from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from httpx import HTTPError, HTTPStatusError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.domains.document import DocumentDomain
from app.use_cases import DeleteDocumentUseCase, IngestDocumentUseCase
from model.document import (
    DeleteDocumentResponse,
    DownloadDocumentRequest,
    DownloadDocumentResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def get_ingest_document_use_case() -> IngestDocumentUseCase:
    return IngestDocumentUseCase(
        openai_api_key=settings.openai_api_key,
        qdrant_url=settings.qdrant_url,
        qdrant_api_key=settings.qdrant_api_key,
        qdrant_collection=settings.qdrant_collection,
        embedding_model=settings.openai_embedding_model,
        embedding_dimensions=settings.openai_embedding_dimensions,
    )


def get_delete_document_use_case() -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(
        qdrant_url=settings.qdrant_url,
        qdrant_collection=settings.qdrant_collection,
    )


def get_document_domain(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> DocumentDomain:
    return DocumentDomain(session)


@router.post("/download", response_model=DownloadDocumentResponse)
async def download_document(
    payload: DownloadDocumentRequest,
    use_case: Annotated[
        IngestDocumentUseCase,
        Depends(get_ingest_document_use_case),
    ],
    document_domain: Annotated[DocumentDomain, Depends(get_document_domain)],
) -> DownloadDocumentResponse:
    document = await document_domain.create_processing_document(payload.url.strip())

    try:
        result = await use_case.execute(payload.url.strip(), document_id=document.id)
        await document_domain.mark_document_indexed(
            document,
            result.filename,
            result.path,
            result.chunks_indexed,
        )
    except ValueError as error:
        await document_domain.mark_document_error(document)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except HTTPStatusError as error:
        await document_domain.mark_document_error(document)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nao foi possivel baixar o documento: HTTP {error.response.status_code}.",
        ) from error
    except HTTPError as error:
        await document_domain.mark_document_error(document)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel baixar o documento.",
        ) from error
    except RuntimeError as error:
        await document_domain.mark_document_error(document)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return DownloadDocumentResponse(
        filename=result.filename,
        path=str(Path(result.path).resolve()),
        chunks_indexed=result.chunks_indexed,
    )


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    document_id: str,
    use_case: Annotated[
        DeleteDocumentUseCase,
        Depends(get_delete_document_use_case),
    ],
) -> DeleteDocumentResponse:
    try:
        result = await use_case.execute(document_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return DeleteDocumentResponse(
        document_id=result.document_id,
        deleted=True,
    )
