from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.db.qdrant import build_qdrant_client


@dataclass(frozen=True)
class DeleteDocumentResult:
    document_id: str


class DeleteDocumentUseCase:
    def __init__(
        self,
        qdrant_url: str | None,
        qdrant_collection: str,
        qdrant_client: QdrantClient | None = None,
    ) -> None:
        self._qdrant_url = qdrant_url
        self._qdrant_collection = qdrant_collection
        self._qdrant_client = qdrant_client

    async def execute(self, document_id: str) -> DeleteDocumentResult:
        sanitized_document_id = document_id.strip()

        if not sanitized_document_id:
            raise ValueError("Informe o id do documento.")

        if not self._qdrant_url and self._qdrant_client is None:
            raise RuntimeError("QDRANT_URL nao configurada no back-end.")

        client = self._qdrant_client or build_qdrant_client()
        client.delete(
            collection_name=self._qdrant_collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="metadata.document_id",
                        match=MatchValue(value=sanitized_document_id),
                    ),
                ],
            ),
            wait=True,
        )

        return DeleteDocumentResult(document_id=sanitized_document_id)
