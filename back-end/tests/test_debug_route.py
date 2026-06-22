import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from app.app import app


class FakeVectorStore:
    def __init__(self, results) -> None:
        self.results = results
        self.calls = []

    def similarity_search_with_score(self, query: str, **kwargs):
        self.calls.append((query, kwargs))
        return self.results


class FakeRetriever:
    def __init__(self, results) -> None:
        self.results = results
        self.calls = []

    def invoke(self, query: str):
        self.calls.append(query)
        return self.results


class DebugRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_test_route_returns_recovered_chunks(self) -> None:
        document = Document(
            page_content="3.2 Cotas\n\nConteudo recuperado",
            metadata={
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "title": "Calendario",
                "source_url": "https://example.com/doc.pdf",
                "type": "paragraph",
                "page": 2,
                "page_numbers": [2],
                "section_path": ["3 Cursos", "3.2 Cotas"],
                "bounding_boxes": [{"page": 2, "x0": 1, "y0": 2, "x1": 3, "y1": 4}],
            },
        )
        vector_store = FakeVectorStore(
            [
                (
                    document,
                    0.77,
                ),
            ],
        )
        retriever = FakeRetriever([document])

        with patch(
            "app.routes.test.build_qdrant_vector_store",
            return_value=vector_store,
        ), patch(
            "app.routes.test.build_qdrant_retriever",
            return_value=retriever,
        ):
            response = self.client.post(
                "/test",
                json={"query": "quais sao os prazos?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            vector_store.calls[0][1]["hybrid_fusion"].fusion.value,
            "dbsf",
        )
        self.assertEqual(response.json()["raw_results"][0]["score"], 0.77)
        self.assertIsNone(response.json()["mmr_results"][0]["score"])
        self.assertIsNone(response.json()["reranked_results"][0]["score"])
        self.assertEqual(response.json()["raw_results"][0]["text"], "3.2 Cotas\n\nConteudo recuperado")
        self.assertEqual(response.json()["mmr_results"][0]["text"], "3.2 Cotas\n\nConteudo recuperado")
        self.assertEqual(response.json()["reranked_results"][0]["section_path"], ["3 Cursos", "3.2 Cotas"])

    def test_test_route_rejects_empty_query(self) -> None:
        response = self.client.post(
            "/test",
            json={"query": "   "},
        )

        self.assertEqual(response.status_code, 400)

if __name__ == "__main__":
    unittest.main()
