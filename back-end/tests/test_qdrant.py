import unittest
from types import SimpleNamespace

from qdrant_client.models import Modifier

from app.db.qdrant import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    ensure_qdrant_collection,
)
from app.config import settings


class FakeQdrantClient:
    def __init__(self, collection_exists: bool) -> None:
        self._collection_exists = collection_exists
        self.created_collection = None

    def collection_exists(self, collection_name: str) -> bool:
        return self._collection_exists

    def create_collection(self, **kwargs) -> None:
        self.created_collection = kwargs

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

    def test_rejects_existing_collection_without_sparse_vector(self) -> None:
        client = FakeQdrantClient(collection_exists=True)

        with self.assertRaisesRegex(RuntimeError, "sparse"):
            ensure_qdrant_collection(client)


if __name__ == "__main__":
    unittest.main()
