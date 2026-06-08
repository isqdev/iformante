from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from app.config import settings

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
SPARSE_MODEL_NAME = "Qdrant/bm25"
TOP_K_DEFAULT = 10


def build_qdrant_client() -> QdrantClient:
    if not settings.qdrant_url:
        raise RuntimeError("QDRANT_URL nao configurada no back-end.")

    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )


def build_dense_embeddings() -> OpenAIEmbeddings:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

    return OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
        dimensions=settings.openai_embedding_dimensions,
    )


def build_sparse_embeddings() -> FastEmbedSparse:
    return FastEmbedSparse(model_name=SPARSE_MODEL_NAME)


def ensure_qdrant_collection(client: QdrantClient) -> None:
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
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
        return

    collection = client.get_collection(settings.qdrant_collection)
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


def build_qdrant_vector_store() -> QdrantVectorStore:
    client = build_qdrant_client()
    ensure_qdrant_collection(client)

    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection,
        embedding=build_dense_embeddings(),
        sparse_embedding=build_sparse_embeddings(),
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name=DENSE_VECTOR_NAME,
        sparse_vector_name=SPARSE_VECTOR_NAME,
    )


def build_qdrant_retriever(top_k: int | None = None) -> VectorStoreRetriever:
    vector_store = build_qdrant_vector_store()

    return vector_store.as_retriever(
        search_kwargs={
            "k": top_k or TOP_K_DEFAULT,
        },
    )
