from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from httpx import HTTPError, HTTPStatusError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models import User
from app.security.dependencies import require_admin, optional_current_user
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
    RenameDocumentRequest,
)
from app.use_cases import DeleteDocumentUseCase
from app.use_cases.documents import ListDocumentsUseCase
from app.use_cases.documents import PdfUploadIngestUseCase, WebPageIngestUseCase
from app.repositories import DocumentRepository
from app.services.remote_document import remote_document_response

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/content", response_class=FileResponse, response_model=None)
async def get_document_content(
    document_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    user: Annotated[User | None, Depends(optional_current_user)],
) -> FileResponse | StreamingResponse:
    document = await DocumentRepository(session).get_by_id(document_id)

    if document is None or not document.stored_path or (document.ingestion_status != "INDEXED" and (not user or user.role != "ADMIN")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento nao encontrado.")

    storage_root = Path(settings.document_storage_dir).resolve()
    stored_path = Path(document.stored_path).resolve()

    if not stored_path.is_relative_to(storage_root) or not stored_path.is_file():
        # Uploaded originals keep the same document ID across deployments.
        stored_path = (storage_root / document.id / "original.pdf").resolve()
        if not stored_path.is_relative_to(storage_root) or not stored_path.is_file():
            if settings.document_remote_base_url:
                return await remote_document_response(settings.document_remote_base_url, document.id, request)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo PDF nao encontrado.")

    if stored_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="O arquivo armazenado nao e um PDF.")

    return FileResponse(
        stored_path,
        media_type="application/pdf",
        filename=document.file_name or stored_path.name,
        content_disposition_type="inline",
    )


@router.get("")
async def list_documents(
    user: Annotated[User | None, Depends(optional_current_user)],
    use_case: Annotated[
        ListDocumentsUseCase,
        Depends(get_list_documents_use_case),
    ],
) -> list[dict]:
    documents = await use_case.execute(public=not user or user.role != "ADMIN")
    if user and user.role == "ADMIN":
        return [DocumentResponse(id=d.id, name=d.title, url=d.source_url, source_type=d.source_type, status=d.ingestion_status, uploaded_by_name=d.uploaded_by_user.name.split(maxsplit=1)[0]).model_dump() for d in documents]
    return [{"id": d.id, "name": d.title, "url": d.source_url, "source_type": d.source_type} for d in documents if d.ingestion_status == "INDEXED"]



@router.post("/upload", response_model=IngestDocumentResponse)
async def upload_document(
    admin: Annotated[User, Depends(require_admin)],
    use_case: Annotated[
        PdfUploadIngestUseCase,
        Depends(get_pdf_upload_ingest_use_case),
    ],
    file: UploadFile = File(...),
    title: str = Form(...),
) -> IngestDocumentResponse:
    try:
        result = await use_case.execute(file, title, admin.id)
    except IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um documento com este nome.") from error
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
    admin: Annotated[User, Depends(require_admin)],
    payload: CreateWebPageRequest,
    use_case: Annotated[
        WebPageIngestUseCase,
        Depends(get_web_page_ingest_use_case),
    ],
) -> IngestDocumentResponse:
    try:
        result = await use_case.execute(payload.url, admin.id, payload.title)
    except IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta página já foi adicionada.") from error
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


@router.post("/metadata")
async def document_metadata(payload: CreateWebPageRequest, admin: Annotated[User, Depends(require_admin)]):
    from app.services import WebPageExtractor
    try:
        extracted = await WebPageExtractor().extract(payload.url)
        return {"title": extracted.title, "url": payload.url, "source_type": "WEB_PAGE"}
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except HTTPError as error:
        raise HTTPException(502, "Não foi possível consultar a página.") from error


@router.patch("/{document_id}", response_model=DocumentResponse)
async def rename_document(
    admin: Annotated[User, Depends(require_admin)],
    document_id: str,
    payload: RenameDocumentRequest,
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> DocumentResponse:
    repository = DocumentRepository(session)
    document = await repository.get_by_id(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento nao encontrado.")

    document = await repository.rename(document, payload.title.strip())
    await session.commit()
    return DocumentResponse(
        id=document.id,
        name=document.title,
        url=document.source_url,
        source_type=document.source_type,
        status=document.ingestion_status,
        uploaded_by_name=document.uploaded_by_user.name.split(maxsplit=1)[0],
    )


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    admin: Annotated[User, Depends(require_admin)],
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
