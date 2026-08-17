import unittest

from app.rag.retrieval import ChildReranker


class ChildRerankerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reranker = ChildReranker("test-key")

    def test_accepts_only_known_unique_pseudo_ids_and_appends_omissions(
        self,
    ) -> None:
        result = self.reranker._validate_order(
            ["child_3", "realRandomId", "child_1", "child_3"],
            ["child_1", "child_2", "child_3"],
        )

        self.assertEqual(result, ["child_3", "child_1", "child_2"])

    def test_parser_requires_a_bare_json_array(self) -> None:
        self.assertEqual(
            self.reranker._parse_array('["child_2", "child_1"]'),
            ["child_2", "child_1"],
        )
        self.assertEqual(
            self.reranker._parse_array('{"chunks": ["child_1"]}'),
            [],
        )
        self.assertEqual(
            self.reranker._parse_array('```json\n["child_1"]\n```'),
            [],
        )

    def test_uses_the_configured_model(self) -> None:
        reranker = ChildReranker("test-key", "gpt-4.1-nano")

        self.assertEqual(reranker._model.model_name, "gpt-4.1-nano")


if __name__ == "__main__":
    unittest.main()
