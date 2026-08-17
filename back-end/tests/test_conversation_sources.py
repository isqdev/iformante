import unittest
from types import SimpleNamespace

from app.routes.conversation import _message_sources


class ConversationSourcesTests(unittest.TestCase):
    def test_serializes_and_deduplicates_persisted_sources(self) -> None:
        document = SimpleNamespace(
            source_url="https://example.com/document.pdf",
            file_name="document.pdf",
            title="Document",
        )
        message = SimpleNamespace(
            sources=[
                SimpleNamespace(document=document),
                SimpleNamespace(document=document),
            ],
        )

        sources = _message_sources(message)

        self.assertEqual(
            [source.model_dump() for source in sources],
            [
                {
                    "filename": "document.pdf",
                    "url": "https://example.com/document.pdf",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
