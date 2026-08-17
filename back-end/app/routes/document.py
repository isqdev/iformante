from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from httpx import HTTPError, HTTPStatusError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db import get_database_session
from app.factories.documents import (
    get_delete_document_use_case,
    get_ingest_document_use_case,
    get_list_documents_use_case,
)
from app.dtos import (
    DeleteDocumentResponse,
    DocumentResponse,
    DownloadDocumentRequest,
    DownloadDocumentResponse,
)
from app.use_cases import DeleteDocumentUseCase, IngestDocumentUseCase
from app.use_cases.documents import ListDocumentsUseCase
from app.repositories import DocumentRepository

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/content", response_class=FileResponse)
async def get_document_content(
    document_id: str,
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> FileResponse:
    document = await DocumentRepository(session).get_by_id(document_id)

    if document is None or not document.stored_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento nao encontrado.")

    storage_root = Path(settings.document_storage_dir).resolve()
    stored_path = Path(document.stored_path).resolve()

    if not stored_path.is_relative_to(storage_root) or not stored_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo PDF nao encontrado.")

    if stored_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="O arquivo armazenado nao e um PDF.")

    return FileResponse(
        stored_path,
        media_type="application/pdf",
        filename=document.file_name or stored_path.name,
        content_disposition_type="inline",
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    use_case: Annotated[
        ListDocumentsUseCase,
        Depends(get_list_documents_use_case),
    ],
) -> list[DocumentResponse]:
    documents = await use_case.execute()
    return [
        DocumentResponse(
            id=document.id,
            name=document.file_name or document.title,
            url=document.source_url,
        )
        for document in documents
    ]


@router.post("/download", response_model=DownloadDocumentResponse)
async def download_document(
    payload: DownloadDocumentRequest,
    use_case: Annotated[
        IngestDocumentUseCase,
        Depends(get_ingest_document_use_case),
    ],
) -> DownloadDocumentResponse:
    try:
        result = await use_case.execute(payload.url.strip())
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except HTTPStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nao foi possivel baixar o documento: HTTP {error.response.status_code}.",
        ) from error
    except HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel baixar o documento.",
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return DownloadDocumentResponse(
        filename=result.filename,
        path=result.storage_url,
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
