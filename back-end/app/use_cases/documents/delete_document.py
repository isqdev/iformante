import asyncio
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

from app.db.qdrant import build_qdrant_client, delete_parent_documents_by_document_id
from app.use_cases.documents.document_manager import DocumentManager


@dataclass(frozen=True)
class DeleteDocumentResult:
    document_id: str


class DeleteDocumentUseCase:
    def __init__(
        self,
        qdrant_url: str | None,
        qdrant_collection: str,
        document_manager: DocumentManager,
        cloudinary_cloud_name: str | None,
        cloudinary_api_key: str | None,
        cloudinary_api_secret: str | None,
        qdrant_client: QdrantClient | None = None,
    ) -> None:
        self._qdrant_url = qdrant_url
        self._qdrant_collection = qdrant_collection
        self._document_manager = document_manager
        self._cloudinary_cloud_name = cloudinary_cloud_name
        self._cloudinary_api_key = cloudinary_api_key
        self._cloudinary_api_secret = cloudinary_api_secret
        self._qdrant_client = qdrant_client

    async def execute(self, document_id: str) -> DeleteDocumentResult:
        sanitized_document_id = document_id.strip()

        if not sanitized_document_id:
            raise ValueError("Informe o id do documento.")

        if not self._qdrant_url and self._qdrant_client is None:
            raise RuntimeError("QDRANT_URL nao configurada no back-end.")

        document = await self._document_manager.get_document(sanitized_document_id)

        if document is None:
            raise ValueError("Documento nao encontrado.")

        await self._delete_from_cloudinary(document.id, document.file_name)

        client = self._qdrant_client or build_qdrant_client()

        client.delete(
            collection_name=self._qdrant_collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="metadata.document_id",
                            match=MatchValue(value=sanitized_document_id),
                        ),
                    ],
                )
            ),
            wait=True,
        )
        delete_parent_documents_by_document_id(
            sanitized_document_id,
            qdrant_client=client,
        )
        await self._document_manager.delete_document(document)

        return DeleteDocumentResult(document_id=sanitized_document_id)

    async def _delete_from_cloudinary(self, document_id: str, file_name: str) -> None:
        if not all(
            (
                self._cloudinary_cloud_name,
                self._cloudinary_api_key,
                self._cloudinary_api_secret,
            ),
        ):
            raise RuntimeError("Credenciais do Cloudinary nao configuradas no back-end.")

        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=self._cloudinary_cloud_name,
            api_key=self._cloudinary_api_key,
            api_secret=self._cloudinary_api_secret,
            secure=True,
        )
        result = await asyncio.to_thread(
            cloudinary.uploader.destroy,
            f"iformante/documents/{document_id}/{file_name}",
            resource_type="raw",
            invalidate=True,
        )

        if result.get("result") not in {"ok", "not found"}:
            raise RuntimeError("Nao foi possivel excluir o documento do Cloudinary.")
