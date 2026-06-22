from functools import lru_cache
import math
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.retrievers import BaseRetriever
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    Fusion,
    FusionQuery,
    MatchAny,
    MatchValue,
    Modifier,
    PayloadSchemaType,
    PointStruct,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from app.config import settings

DENSE_VECTOR_NAME = "dense"
PARENT_VECTOR_NAME = "parent"
SPARSE_VECTOR_NAME = "sparse"
SPARSE_MODEL_NAME = "Qdrant/bm25"
RERANKER_MODEL_NAME = "gpt-4.1-mini"
TOP_K_DEFAULT = 8
RERANK_CANDIDATE_MULTIPLIER = 4
MMR_LAMBDA_MULT = 0.7
MMR_CANDIDATE_MULTIPLIER = 2


class ChunkRanking(BaseModel):
    indexes: list[int] = Field(
        description="Indices dos chunks em ordem decrescente de relevancia.",
    )


class OpenAIReranker:
    def __init__(self, model_name: str) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

        self._model = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=model_name,
            temperature=0,
        ).with_structured_output(ChunkRanking)

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int,
    ) -> list[int]:
        result = self._model.invoke(
            [
                SystemMessage(
                    content=(
                        "Voce e o reranker do IFormante. Ordene os chunks pela "
                        "capacidade de responder diretamente a consulta. Considere "
                        "regras, excecoes, tabelas e correspondencia institucional. "
                        "Retorne exatamente os indices dos chunks mais relevantes, "
                        "sem repetir indices."
                    ),
                ),
                HumanMessage(
                    content=_build_reranker_input(query, documents, top_k),
                ),
            ],
        )
        requested_count = min(top_k, len(documents))
        indexes = _normalize_ranked_indexes(
            result.indexes,
            document_count=len(documents),
        )

        if len(indexes) < requested_count:
            indexes.extend(
                index
                for index in range(len(documents))
                if index not in indexes
            )

        return indexes[:requested_count]


class RerankingRetriever(BaseRetriever):
    base_retriever: Any
    parent_collection_name: str = ""
    reranker: Any
    top_k: int

    def _get_relevant_documents(self, query: str) -> list[Document]:
        documents = self.base_retriever.invoke(query)
        print(
            f"[IFormante][Retriever] children_retrieved={len(documents)}",
            flush=True,
        )
        documents = apply_mmr_to_documents(
            query=query,
            documents=documents,
            top_k=max(self.top_k, self.top_k * MMR_CANDIDATE_MULTIPLIER),
        )
        print(
            f"[IFormante][Retriever] children_after_mmr={len(documents)}",
            flush=True,
        )

        if not documents:
            return []

        try:
            ranked_indexes = self.reranker.rerank(
                query=query,
                documents=[document.page_content for document in documents],
                top_k=self.top_k,
            )
            ranked_documents = [documents[index] for index in ranked_indexes]
        except Exception as error:
            print(
                "[IFormante][Retriever] llm_reranker_failed "
                f"error={error!r} fallback=mmr_order",
                flush=True,
            )
            ranked_documents = documents[: self.top_k]

        reranked_children = _select_parent_diverse_children(
            ranked_documents,
            self.top_k,
        )
        parent_documents = fetch_parent_documents(
            reranked_children,
            self.parent_collection_name,
        )
        return parent_documents


def _select_parent_diverse_children(
    documents: list[Document],
    top_k: int,
) -> list[Document]:
    selected: list[Document] = []
    deferred: list[Document] = []
    seen_parent_ids: set[str] = set()

    for document in documents:
        parent_id = str(document.metadata.get("parent_id") or "").strip()

        if parent_id and parent_id in seen_parent_ids:
            deferred.append(document)
            continue

        selected.append(document)

        if parent_id:
            seen_parent_ids.add(parent_id)

        if len(selected) == top_k:
            return selected

    for document in deferred:
        selected.append(document)

        if len(selected) == top_k:
            break

    return selected


def _build_reranker_input(
    query: str,
    documents: list[str],
    top_k: int,
) -> str:
    chunks = "\n\n".join(
        f"CHUNK {index}\n{document}"
        for index, document in enumerate(documents)
    )
    requested_count = min(top_k, len(documents))
    return (
        f"CONSULTA:\n{query}\n\n"
        f"Selecione e ordene exatamente {requested_count} chunks. "
        "Os indices comecam em 0.\n\n"
        f"CHUNKS:\n{chunks}"
    )


def _normalize_ranked_indexes(
    indexes: list[int],
    document_count: int,
) -> list[int]:
    normalized: list[int] = []

    for index in indexes:
        if index < 0 or index >= document_count or index in normalized:
            continue

        normalized.append(index)

    return normalized


def _print_selected_children(documents: list[Document]) -> None:
    for index, document in enumerate(documents, start=1):
        metadata = document.metadata
        print(
            "\n".join(
                [
                    "[IFormante][Retriever][Child]",
                    f"index={index}/{len(documents)}",
                    f"chunk_id={metadata.get('chunk_id') or '<none>'}",
                    f"parent_id={metadata.get('parent_id') or '<none>'}",
                    "text:",
                    document.page_content,
                    "-" * 80,
                ],
            ),
            flush=True,
        )


@lru_cache(maxsize=1)
def build_qdrant_client() -> QdrantClient:
    if not settings.qdrant_url:
        raise RuntimeError("QDRANT_URL nao configurada no back-end.")

    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )


@lru_cache(maxsize=1)
def build_dense_embeddings() -> OpenAIEmbeddings:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

    return OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
        dimensions=settings.openai_embedding_dimensions,
    )


@lru_cache(maxsize=1)
def build_sparse_embeddings() -> FastEmbedSparse:
    return FastEmbedSparse(model_name=SPARSE_MODEL_NAME)


def build_hybrid_fusion_query() -> FusionQuery:
    return FusionQuery(fusion=Fusion.DBSF)


@lru_cache(maxsize=1)
def build_reranker() -> OpenAIReranker:
    return OpenAIReranker(model_name=RERANKER_MODEL_NAME)


def apply_mmr_to_documents(
    query: str,
    documents: list[Document],
    top_k: int,
    lambda_mult: float = MMR_LAMBDA_MULT,
) -> list[Document]:
    if len(documents) <= top_k:
        return documents

    document_embeddings = _extract_document_embeddings(documents)

    if len(document_embeddings) != len(documents):
        document_embeddings = _retrieve_document_embeddings(documents)

    if len(document_embeddings) != len(documents):
        return documents

    query_embedding = build_dense_embeddings().embed_query(query)
    selected_indexes = _max_marginal_relevance(
        query_embedding=query_embedding,
        document_embeddings=document_embeddings,
        top_k=top_k,
        lambda_mult=lambda_mult,
    )

    return [documents[index] for index in selected_indexes]


def _extract_document_embeddings(documents: list[Document]) -> list[list[float]]:
    embeddings: list[list[float]] = []

    for document in documents:
        embedding = _extract_document_embedding(document)

        if embedding is None:
            return []

        embeddings.append(embedding)

    return embeddings


def _extract_document_embedding(document: Document) -> list[float] | None:
    metadata = document.metadata
    candidate = (
        metadata.get("_embedding")
        or metadata.get("_embeddings")
        or metadata.get("embedding")
        or metadata.get(DENSE_VECTOR_NAME)
    )

    if candidate is None and isinstance(metadata.get("_vectors"), dict):
        candidate = metadata["_vectors"].get(DENSE_VECTOR_NAME)

    if candidate is None and isinstance(metadata.get("vectors"), dict):
        candidate = metadata["vectors"].get(DENSE_VECTOR_NAME)

    return _normalize_dense_vector(candidate)


def _retrieve_document_embeddings(documents: list[Document]) -> list[list[float]]:
    point_ids = [
        document.metadata.get("_id")
        for document in documents
        if document.metadata.get("_id") is not None
    ]

    if len(point_ids) != len(documents):
        return []

    collection_name = str(
        documents[0].metadata.get("_collection_name") or settings.qdrant_collection,
    )
    client = build_qdrant_client()
    points = client.retrieve(
        collection_name=collection_name,
        ids=point_ids,
        with_payload=False,
        with_vectors=True,
    )
    vectors_by_id = {
        str(point.id): _extract_point_dense_vector(point.vector)
        for point in points
    }
    embeddings: list[list[float]] = []

    for point_id in point_ids:
        embedding = vectors_by_id.get(str(point_id))

        if embedding is None:
            return []

        embeddings.append(embedding)

    return embeddings


def _extract_point_dense_vector(vector: Any) -> list[float] | None:
    if isinstance(vector, dict):
        return _normalize_dense_vector(vector.get(DENSE_VECTOR_NAME))

    return _normalize_dense_vector(vector)


def _normalize_dense_vector(vector: Any) -> list[float] | None:
    if not isinstance(vector, list):
        return None

    normalized_vector: list[float] = []

    for value in vector:
        if not isinstance(value, int | float):
            return None

        normalized_vector.append(float(value))

    return normalized_vector


def _max_marginal_relevance(
    query_embedding: list[float],
    document_embeddings: list[list[float]],
    top_k: int,
    lambda_mult: float,
) -> list[int]:
    selected_indexes: list[int] = []
    candidate_indexes = list(range(len(document_embeddings)))
    query_similarities = [
        _cosine_similarity(query_embedding, document_embedding)
        for document_embedding in document_embeddings
    ]

    while candidate_indexes and len(selected_indexes) < top_k:
        if not selected_indexes:
            next_index = max(
                candidate_indexes,
                key=lambda index: query_similarities[index],
            )
        else:
            next_index = max(
                candidate_indexes,
                key=lambda index: (
                    lambda_mult * query_similarities[index]
                    - (1 - lambda_mult)
                    * max(
                        _cosine_similarity(
                            document_embeddings[index],
                            document_embeddings[selected_index],
                        )
                        for selected_index in selected_indexes
                    )
                ),
            )

        selected_indexes.append(next_index)
        candidate_indexes.remove(next_index)

    return selected_indexes


def _cosine_similarity(first_embedding: list[float], second_embedding: list[float]) -> float:
    dot_product = sum(
        first_value * second_value
        for first_value, second_value in zip(
            first_embedding,
            second_embedding,
            strict=True,
        )
    )
    first_norm = math.sqrt(
        sum(first_value * first_value for first_value in first_embedding),
    )
    second_norm = math.sqrt(
        sum(second_value * second_value for second_value in second_embedding),
    )

    if first_norm == 0 or second_norm == 0:
        return 0

    return dot_product / (first_norm * second_norm)


def ensure_qdrant_collection(
    client: QdrantClient,
    collection_name: str | None = None,
) -> None:
    resolved_collection_name = collection_name or settings.qdrant_collection

    if not client.collection_exists(resolved_collection_name):
        client.create_collection(
            collection_name=resolved_collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(
                    size=settings.openai_embedding_dimensions,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: SparseVectorParams(
                    index=SparseIndexParams(on_disk=True),
                    modifier=Modifier.IDF,
                ),
            },
        )
        ensure_qdrant_payload_indexes(client, resolved_collection_name)
        return

    collection = client.get_collection(resolved_collection_name)
    vectors_config = collection.config.params.vectors
    sparse_vectors_config = collection.config.params.sparse_vectors

    if not isinstance(vectors_config, dict) or DENSE_VECTOR_NAME not in vectors_config:
        raise RuntimeError(
            "A collection do Qdrant precisa ter um vetor dense nomeado 'dense'.",
        )

    dense_vector = vectors_config[DENSE_VECTOR_NAME]
    if dense_vector.size != settings.openai_embedding_dimensions:
        raise RuntimeError(
            "A collection do Qdrant usa dimensoes dense incompativeis com o back-end.",
        )

    if sparse_vectors_config is None or SPARSE_VECTOR_NAME not in sparse_vectors_config:
        raise RuntimeError(
            "A collection do Qdrant precisa ter um vetor sparse nomeado 'sparse'.",
        )

    ensure_qdrant_payload_indexes(client, resolved_collection_name)


def get_parent_collection_name(collection_name: str | None = None) -> str:
    return f"{collection_name or settings.qdrant_collection}-parents"


def ensure_qdrant_parent_collection(
    client: QdrantClient,
    collection_name: str | None = None,
) -> None:
    resolved_collection_name = collection_name or get_parent_collection_name()

    if not client.collection_exists(resolved_collection_name):
        client.create_collection(
            collection_name=resolved_collection_name,
            vectors_config={
                PARENT_VECTOR_NAME: VectorParams(
                    size=1,
                    distance=Distance.COSINE,
                ),
            },
        )
        client.create_payload_index(
            collection_name=resolved_collection_name,
            field_name="document_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        return

    client.create_payload_index(
        collection_name=resolved_collection_name,
        field_name="document_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )


def upsert_parent_documents(
    parents: list[Document],
    collection_name: str | None = None,
) -> None:
    if not parents:
        return

    client = build_qdrant_client()
    parent_collection_name = collection_name or get_parent_collection_name()
    ensure_qdrant_parent_collection(client, parent_collection_name)
    points: list[PointStruct] = []

    for parent in parents:
        parent_id = str(parent.metadata.get("parent_id") or "").strip()

        if not parent_id:
            continue

        points.append(
            PointStruct(
                id=parent_id,
                vector={PARENT_VECTOR_NAME: [0.0]},
                payload={
                    **parent.metadata,
                    "text": parent.page_content,
                },
            ),
        )

    if points:
        client.upsert(
            collection_name=parent_collection_name,
            points=points,
            wait=True,
        )


def fetch_parent_documents(
    child_documents: list[Document],
    collection_name: str | None = None,
) -> list[Document]:
    parent_ids: list[str] = []
    seen_parent_ids: set[str] = set()

    for document in child_documents:
        parent_id = str(document.metadata.get("parent_id") or "").strip()

        if not parent_id or parent_id in seen_parent_ids:
            continue

        seen_parent_ids.add(parent_id)
        parent_ids.append(parent_id)

    if not parent_ids:
        return child_documents

    client = build_qdrant_client()
    parent_collection_name = collection_name or get_parent_collection_name()
    ensure_qdrant_parent_collection(client, parent_collection_name)
    points = client.retrieve(
        collection_name=parent_collection_name,
        ids=parent_ids,
        with_payload=True,
        with_vectors=False,
    )
    points_by_id = {str(point.id): point for point in points}
    parent_documents: list[Document] = []

    for parent_id in parent_ids:
        point = points_by_id.get(parent_id)

        if not point or not point.payload:
            continue

        payload = dict(point.payload)
        text = str(payload.pop("text", ""))

        if not text:
            continue

        parent_documents.append(
            Document(
                page_content=text,
                metadata=payload,
            ),
        )

    return parent_documents or child_documents


def delete_parent_documents_by_document_id(
    document_id: str,
    collection_name: str | None = None,
    qdrant_client: QdrantClient | None = None,
) -> None:
    client = qdrant_client or build_qdrant_client()
    parent_collection_name = collection_name or get_parent_collection_name()

    if not client.collection_exists(parent_collection_name):
        return

    client.delete(
        collection_name=parent_collection_name,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    ),
                ],
            ),
        ),
        wait=True,
    )


def ensure_qdrant_payload_indexes(
    client: QdrantClient,
    collection_name: str,
) -> None:
    client.create_payload_index(
        collection_name=collection_name,
        field_name="metadata.document_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )


@lru_cache(maxsize=1)
def build_qdrant_vector_store() -> QdrantVectorStore:
    return build_qdrant_vector_store_for_collection(
        settings.qdrant_collection,
        RetrievalMode.HYBRID,
    )


@lru_cache(maxsize=8)
def build_qdrant_vector_store_for_collection(
    collection_name: str,
    retrieval_mode: RetrievalMode,
) -> QdrantVectorStore:
    client = build_qdrant_client()
    ensure_qdrant_collection(client, collection_name)
    sparse_embedding = (
        build_sparse_embeddings()
        if retrieval_mode == RetrievalMode.HYBRID
        else None
    )
    sparse_vector_name = (
        SPARSE_VECTOR_NAME
        if retrieval_mode == RetrievalMode.HYBRID
        else None
    )

    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=build_dense_embeddings(),
        sparse_embedding=sparse_embedding,
        retrieval_mode=retrieval_mode,
        vector_name=DENSE_VECTOR_NAME,
        sparse_vector_name=sparse_vector_name,
    )


@lru_cache(maxsize=16)
def build_qdrant_retriever(
    top_k: int | None = None,
    document_ids: tuple[str, ...] = (),
) -> BaseRetriever:
    vector_store = build_qdrant_vector_store()
    final_top_k = top_k or TOP_K_DEFAULT
    candidate_top_k = max(
        final_top_k,
        final_top_k * RERANK_CANDIDATE_MULTIPLIER,
    )
    search_kwargs: dict[str, Any] = {
        "hybrid_fusion": build_hybrid_fusion_query(),
        "k": candidate_top_k,
    }

    if document_ids:
        search_kwargs["filter"] = Filter(
            must=[
                FieldCondition(
                    key="metadata.document_id",
                    match=MatchAny(any=list(document_ids)),
                ),
            ],
        )

    base_retriever = vector_store.as_retriever(search_kwargs=search_kwargs)

    return RerankingRetriever(
        base_retriever=base_retriever,
        parent_collection_name=get_parent_collection_name(),
        reranker=build_reranker(),
        top_k=final_top_k,
    )
