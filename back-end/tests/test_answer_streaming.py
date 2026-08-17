import unittest
from unittest.mock import patch

from app.rag.generation import AnswerDelta, AnswerGenerator, AnswerResult
from app.rag.retrieval import RetrievedParent


class FakeStreamingModel:
    async def astream(self, messages):
        for content in [
            "Resposta ",
            "em stream.\n\n```j",
            'son\n{"used_sources": ["parent_1"]}\n```',
        ]:
            yield type("Chunk", (), {"content": content})()


class AnswerStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_streams_visible_text_and_hides_source_metadata(self) -> None:
        generator = AnswerGenerator(api_key="test-key", model="test-model")
        parent = RetrievedParent(
            id="parent001",
            document_id="doc000001",
            content="Conteudo recuperado",
            bbox=None,
            source_url="https://example.com/document.pdf",
            filename="document.pdf",
        )

        with patch.object(
            generator,
            "_get_chat_model",
            return_value=FakeStreamingModel(),
        ):
            events = [
                event
                async for event in generator.stream("Pergunta", [parent])
            ]

        deltas = [
            event.content for event in events if isinstance(event, AnswerDelta)
        ]
        result = next(
            event for event in events if isinstance(event, AnswerResult)
        )

        self.assertGreater(len(deltas), 1)
        self.assertEqual("".join(deltas), "Resposta em stream.\n\n")
        self.assertNotIn("used_sources", "".join(deltas))
        self.assertEqual(result.content, "Resposta em stream.")
        self.assertEqual(result.used_parent_ids, ["parent001"])


if __name__ == "__main__":
    unittest.main()
