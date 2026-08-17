import unittest

from sqlalchemy.dialects import postgresql

from app.repositories import RagRepository


class VectorSearchTests(unittest.TestCase):
    def test_uses_only_pgvector_cosine_distance(self) -> None:
        repository = RagRepository(session=None)  # type: ignore[arg-type]

        statement = repository._build_child_candidates_statement(
            embedding=[0.0] * 1536,
            limit=32,
        )
        sql = str(statement.compile(dialect=postgresql.dialect()))

        self.assertIn("<=>", sql)
        self.assertIn("rag_document_children.content", sql)
        self.assertNotIn("row_number", sql.lower())
        self.assertNotIn("plainto_tsquery", sql)
        self.assertNotIn("@@", sql)

if __name__ == "__main__":
    unittest.main()
