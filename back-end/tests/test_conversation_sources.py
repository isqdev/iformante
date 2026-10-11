import unittest
from types import SimpleNamespace

from app.routes.conversation import _message_sources


class ConversationSourcesTests(unittest.TestCase):
    def test_serializes_and_deduplicates_persisted_sources(self) -> None:
        document = SimpleNamespace(
            source_url="https://example.com/document.pdf",
            file_name="document.pdf",
            title="Document",
            ingestion_status="INDEXED",
            source_type="PDF",
        )
        message = SimpleNamespace(
            sources=[
                SimpleNamespace(document=document, document_id="doc123456", chunk_id="chunk1234", bbox=[{"page":1}]),
                SimpleNamespace(document=document, document_id="doc123456", chunk_id="chunk1234", bbox=[{"page":1}]),
            ],
        )

        sources = _message_sources(message)

        self.assertEqual(
            [source.model_dump() for source in sources],
            [
                {
                    "document_id": "doc123456",
                    "source_type": "PDF",
                    "citations": [{"chunk_id": "chunk1234", "anchors": [{"page": 1}]}],
                    "filename": "document.pdf",
                    "url": "https://example.com/document.pdf",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
