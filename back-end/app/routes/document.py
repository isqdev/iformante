from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from httpx import HTTPError, HTTPStatusError
from app.factories.documents import (
    get_delete_document_use_case,
    get_document_manager,
    get_ingest_document_use_case,
)
from app.schemas import (
    DeleteDocumentResponse,
    DocumentResponse,
    DownloadDocumentRequest,
    DownloadDocumentResponse,
)
from app.use_cases import DeleteDocumentUseCase, DocumentManager, IngestDocumentUseCase

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    document_manager: Annotated[DocumentManager, Depends(get_document_manager)],
) -> list[DocumentResponse]:
    documents = await document_manager.list_documents()
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
    document_domain: Annotated[DocumentManager, Depends(get_document_manager)],
) -> DownloadDocumentResponse:
    document = await document_domain.create_processing_document(payload.url.strip())

    try:
        result = await use_case.execute(payload.url.strip(), document_id=document.id)
        await document_domain.mark_document_indexed(
            document,
            result.filename,
            result.storage_url,
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
