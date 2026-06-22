import unittest
from types import SimpleNamespace

from langchain_core.documents import Document
from langchain_qdrant import RetrievalMode
from qdrant_client.models import Fusion, Modifier

from app.db.qdrant import (
    ChunkRanking,
    DENSE_VECTOR_NAME,
    OpenAIReranker,
    RerankingRetriever,
    SPARSE_VECTOR_NAME,
    _normalize_ranked_indexes,
    _select_parent_diverse_children,
    apply_mmr_to_documents,
    fetch_parent_documents,
    build_hybrid_fusion_query,
    build_qdrant_vector_store,
    build_qdrant_retriever,
    ensure_qdrant_collection,
)
from app.config import settings


class FakeQdrantClient:
    def __init__(self, collection_exists: bool) -> None:
        self._collection_exists = collection_exists
        self.created_collection = None
        self.created_payload_indexes = []

    def collection_exists(self, collection_name: str) -> bool:
        return self._collection_exists

    def create_collection(self, **kwargs) -> None:
        self.created_collection = kwargs

    def create_payload_index(self, **kwargs) -> None:
        self.created_payload_indexes.append(kwargs)

    def get_collection(self, collection_name: str):
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors={
                        DENSE_VECTOR_NAME: SimpleNamespace(
                            size=settings.openai_embedding_dimensions,
                        ),
                    },
                    sparse_vectors={},
                ),
            ),
        )


class QdrantTests(unittest.TestCase):
    def test_creates_hybrid_collection_with_dense_sparse_and_idf(self) -> None:
        client = FakeQdrantClient(collection_exists=False)

        ensure_qdrant_collection(client)

        self.assertEqual(client.created_collection["collection_name"], settings.qdrant_collection)
        self.assertIn(DENSE_VECTOR_NAME, client.created_collection["vectors_config"])
        self.assertIn(SPARSE_VECTOR_NAME, client.created_collection["sparse_vectors_config"])
        self.assertEqual(
            client.created_collection["sparse_vectors_config"][SPARSE_VECTOR_NAME].modifier,
            Modifier.IDF,
        )
        self.assertEqual(
            client.created_payload_indexes[0]["field_name"],
            "metadata.document_id",
        )

    def test_rejects_existing_collection_without_sparse_vector(self) -> None:
        client = FakeQdrantClient(collection_exists=True)

        with self.assertRaisesRegex(RuntimeError, "sparse"):
            ensure_qdrant_collection(client)

    def test_default_vector_store_uses_hybrid_retrieval(self) -> None:
        with unittest.mock.patch(
            "app.db.qdrant.build_qdrant_vector_store_for_collection",
            return_value=SimpleNamespace(),
        ) as builder:
            build_qdrant_vector_store.cache_clear()
            build_qdrant_vector_store()

        self.assertEqual(builder.call_args.args[1], RetrievalMode.HYBRID)

    def test_retriever_applies_llm_reranker_order(self) -> None:
        class FakeRetriever:
            def invoke(self, query: str):
                return [
                    Document(page_content="baixo"),
                    Document(page_content="alto"),
                    Document(page_content="medio"),
                ]

        class FakeReranker:
            def rerank(self, query: str, documents: list[str], top_k: int):
                self.query = query
                self.documents = documents
                self.top_k = top_k
                return [1, 2]

        reranker = FakeReranker()
        retriever = RerankingRetriever(
            base_retriever=FakeRetriever(),
            reranker=reranker,
            top_k=2,
        )

        documents = retriever.invoke("pergunta")

        self.assertEqual(
            [document.page_content for document in documents],
            ["alto", "medio"],
        )
        self.assertEqual(reranker.query, "pergunta")
        self.assertEqual(reranker.top_k, 2)

    def test_normalizes_llm_ranking_indexes(self) -> None:
        indexes = _normalize_ranked_indexes(
            [2, 2, -1, 5, 0, 1],
            document_count=3,
        )

        self.assertEqual(indexes, [2, 0, 1])

    def test_openai_reranker_returns_eight_ordered_indexes(self) -> None:
        reranker = OpenAIReranker.__new__(OpenAIReranker)
        reranker._model = SimpleNamespace(
            invoke=lambda messages: ChunkRanking(
                indexes=[9, 3, 12, 1, 7, 15, 4, 2],
            ),
        )
        documents = [f"chunk {index}" for index in range(16)]

        indexes = reranker.rerank(
            query="criterios de cotas",
            documents=documents,
            top_k=8,
        )

        self.assertEqual(indexes, [9, 3, 12, 1, 7, 15, 4, 2])

    def test_child_selection_prioritizes_distinct_parents(self) -> None:
        documents = [
            Document(page_content="A1", metadata={"parent_id": "parent-a"}),
            Document(page_content="A2", metadata={"parent_id": "parent-a"}),
            Document(page_content="B1", metadata={"parent_id": "parent-b"}),
            Document(page_content="C1", metadata={"parent_id": "parent-c"}),
        ]

        selected = _select_parent_diverse_children(documents, top_k=3)

        self.assertEqual(
            [document.metadata["parent_id"] for document in selected],
            ["parent-a", "parent-b", "parent-c"],
        )

    def test_fetch_parent_documents_deduplicates_in_child_order(self) -> None:
        class FakePoint:
            def __init__(self, point_id: str, payload: dict) -> None:
                self.id = point_id
                self.payload = payload

        class FakeClient:
            def collection_exists(self, collection_name: str) -> bool:
                return True

            def create_payload_index(self, **kwargs) -> None:
                return None

            def retrieve(self, **kwargs):
                self.retrieve_kwargs = kwargs
                return [
                    FakePoint(
                        "parent-2",
                        {
                            "parent_id": "parent-2",
                            "document_id": "doc-1",
                            "text": "Parent 2",
                        },
                    ),
                    FakePoint(
                        "parent-1",
                        {
                            "parent_id": "parent-1",
                            "document_id": "doc-1",
                            "text": "Parent 1",
                        },
                    ),
                ]

        fake_client = FakeClient()
        children = [
            Document(page_content="child", metadata={"parent_id": "parent-1"}),
            Document(page_content="child", metadata={"parent_id": "parent-2"}),
            Document(page_content="child", metadata={"parent_id": "parent-1"}),
        ]

        with unittest.mock.patch(
            "app.db.qdrant.build_qdrant_client",
            return_value=fake_client,
        ):
            parents = fetch_parent_documents(children, "parents")

        self.assertEqual([parent.page_content for parent in parents], ["Parent 1", "Parent 2"])
        self.assertEqual(fake_client.retrieve_kwargs["ids"], ["parent-1", "parent-2"])

    def test_qdrant_retriever_fetches_extra_candidates_before_reranking(self) -> None:
        class FakeVectorStore:
            def __init__(self) -> None:
                self.search_kwargs = None

            def as_retriever(self, search_kwargs):
                self.search_kwargs = search_kwargs
                return SimpleNamespace(invoke=lambda query: [])

        vector_store = FakeVectorStore()

        with unittest.mock.patch(
            "app.db.qdrant.build_qdrant_vector_store",
            return_value=vector_store,
        ), unittest.mock.patch(
            "app.db.qdrant.build_reranker",
            return_value=SimpleNamespace(rerank=lambda query, documents: []),
        ):
            build_qdrant_retriever.cache_clear()
            build_qdrant_retriever(top_k=4)

        self.assertEqual(vector_store.search_kwargs["k"], 16)
        self.assertEqual(
            vector_store.search_kwargs["hybrid_fusion"].fusion,
            Fusion.DBSF,
        )

    def test_hybrid_fusion_query_uses_dbsf(self) -> None:
        self.assertEqual(build_hybrid_fusion_query().fusion, Fusion.DBSF)

    def test_mmr_uses_document_metadata_embeddings_without_reembedding_documents(self) -> None:
        class FakeEmbeddings:
            def embed_query(self, query: str):
                return [1.0, 0.0]

            def embed_documents(self, documents: list[str]):
                raise AssertionError("embed_documents nao deve ser chamado pelo MMR.")

        documents = [
            Document(page_content="A", metadata={"_embedding": [1.0, 0.0]}),
            Document(page_content="B", metadata={"_embedding": [0.9, 0.1]}),
            Document(page_content="C", metadata={"_embedding": [0.0, 1.0]}),
        ]

        with unittest.mock.patch(
            "app.db.qdrant.build_dense_embeddings",
            return_value=FakeEmbeddings(),
        ):
            selected_documents = apply_mmr_to_documents(
                query="pergunta",
                documents=documents,
                top_k=2,
            )

        self.assertEqual(len(selected_documents), 2)

    def test_mmr_retrieves_qdrant_vectors_without_reembedding_documents(self) -> None:
        class FakeEmbeddings:
            def embed_query(self, query: str):
                return [1.0, 0.0]

            def embed_documents(self, documents: list[str]):
                raise AssertionError("embed_documents nao deve ser chamado pelo MMR.")

        class FakePoint:
            def __init__(self, point_id: str, vector: dict[str, list[float]]) -> None:
                self.id = point_id
                self.vector = vector

        class FakeClient:
            def retrieve(self, **kwargs):
                self.retrieve_kwargs = kwargs
                return [
                    FakePoint("point-1", {DENSE_VECTOR_NAME: [1.0, 0.0]}),
                    FakePoint("point-2", {DENSE_VECTOR_NAME: [0.9, 0.1]}),
                    FakePoint("point-3", {DENSE_VECTOR_NAME: [0.0, 1.0]}),
                ]

        documents = [
            Document(
                page_content="A",
                metadata={"_id": "point-1", "_collection_name": "children"},
            ),
            Document(
                page_content="B",
                metadata={"_id": "point-2", "_collection_name": "children"},
            ),
            Document(
                page_content="C",
                metadata={"_id": "point-3", "_collection_name": "children"},
            ),
        ]
        fake_client = FakeClient()

        with unittest.mock.patch(
            "app.db.qdrant.build_dense_embeddings",
            return_value=FakeEmbeddings(),
        ), unittest.mock.patch(
            "app.db.qdrant.build_qdrant_client",
            return_value=fake_client,
        ):
            selected_documents = apply_mmr_to_documents(
                query="pergunta",
                documents=documents,
                top_k=2,
            )

        self.assertEqual(len(selected_documents), 2)
        self.assertEqual(fake_client.retrieve_kwargs["collection_name"], "children")
        self.assertEqual(
            fake_client.retrieve_kwargs["ids"],
            ["point-1", "point-2", "point-3"],
        )
        self.assertFalse(fake_client.retrieve_kwargs["with_payload"])
        self.assertTrue(fake_client.retrieve_kwargs["with_vectors"])


if __name__ == "__main__":
    unittest.main()
