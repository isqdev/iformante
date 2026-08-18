from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from httpx import HTTPError, HTTPStatusError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db import get_database_session
from app.factories.documents import (
    get_delete_document_use_case,
    get_list_documents_use_case,
    get_pdf_upload_ingest_use_case,
    get_web_page_ingest_use_case,
)
from app.dtos import (
    CreateWebPageRequest,
    DeleteDocumentResponse,
    DocumentResponse,
    IngestDocumentResponse,
)
from app.use_cases import DeleteDocumentUseCase
from app.use_cases.documents import ListDocumentsUseCase
from app.use_cases.documents import PdfUploadIngestUseCase, WebPageIngestUseCase
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
            source_type=document.source_type,
        )
        for document in documents
    ]


@router.post("/upload", response_model=IngestDocumentResponse)
async def upload_document(
    use_case: Annotated[
        PdfUploadIngestUseCase,
        Depends(get_pdf_upload_ingest_use_case),
    ],
    file: UploadFile = File(...),
    title: str = Form(...),
) -> IngestDocumentResponse:
    try:
        result = await use_case.execute(file, title)
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

    return IngestDocumentResponse(
        filename=result.filename,
        path=result.storage_url,
        chunks_indexed=result.chunks_indexed,
    )


@router.post("/web-page", response_model=IngestDocumentResponse)
async def ingest_web_page(
    payload: CreateWebPageRequest,
    use_case: Annotated[
        WebPageIngestUseCase,
        Depends(get_web_page_ingest_use_case),
    ],
) -> IngestDocumentResponse:
    try:
        result = await use_case.execute(payload.url)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except HTTPStatusError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nao foi possivel extrair a pagina: HTTP {error.response.status_code}.",
        ) from error
    except HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel extrair a pagina.",
        ) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    return IngestDocumentResponse(
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
