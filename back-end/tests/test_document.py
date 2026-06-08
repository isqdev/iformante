import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.app import app
from app.routes.document import get_document_domain, get_ingest_document_use_case
from app.use_cases.ingest_document import (
    IngestDocumentResult,
    IngestDocumentUseCase,
    TextUnit,
)


class FakeIngestDocumentUseCase:
    async def execute(self, url: str, document_id: str | None = None) -> IngestDocumentResult:
        self.document_id = document_id
        return IngestDocumentResult(
            filename="document-test.pdf",
            path=Path("downloads/document-test.pdf"),
            chunks_indexed=3,
        )


class FakeDocument:
    id = "doc123456"


class FakeDocumentDomain:
    async def create_processing_document(self, source_url: str) -> FakeDocument:
        self.source_url = source_url
        return FakeDocument()

    async def mark_document_indexed(
        self,
        document,
        file_name: str,
        stored_path: Path,
        total_chunks: int,
    ) -> None:
        return None

    async def mark_document_error(self, document) -> None:
        return None


class FakeStreamResponse:
    headers = {"content-type": "text/plain"}

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self):
        yield b"abc"


class FakeStreamContext:
    async def __aenter__(self) -> FakeStreamResponse:
        return FakeStreamResponse()

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None


class DocumentRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_ingest_document_use_case] = FakeIngestDocumentUseCase
        app.dependency_overrides[get_document_domain] = FakeDocumentDomain
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_download_document_returns_saved_file_metadata(self) -> None:
        response = self.client.post(
            "/documents/download",
            json={"url": "https://example.com/file.pdf"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["filename"], "document-test.pdf")
        self.assertEqual(response.json()["chunks_indexed"], 3)

    def test_download_document_rejects_empty_url(self) -> None:
        response = self.client.post("/documents/download", json={"url": ""})

        self.assertEqual(response.status_code, 422)


class IngestDocumentUseCaseTests(unittest.IsolatedAsyncioTestCase):
    def build_use_case(self, storage_dir: Path | None = None) -> IngestDocumentUseCase:
        return IngestDocumentUseCase(
            openai_api_key="test-key",
            qdrant_url="https://qdrant.example",
            qdrant_api_key="test-qdrant-key",
            qdrant_collection="my-collection",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=1536,
            storage_dir=storage_dir,
        )

    async def test_rejects_non_http_url(self) -> None:
        use_case = self.build_use_case()

        with self.assertRaises(ValueError):
            await use_case._download_document("file:///tmp/file.pdf")

    async def test_downloads_file_to_storage_dir(self) -> None:
        with TemporaryDirectory() as temp_dir:
            use_case = self.build_use_case(storage_dir=Path(temp_dir))

            with patch("httpx.AsyncClient.stream", return_value=FakeStreamContext()):
                path, content_type = await use_case._download_document(
                    "https://example.com/file.txt",
                )

            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes(), b"abc")
            self.assertEqual(path.suffix, ".txt")
            self.assertEqual(content_type, "text/plain")

    async def test_builds_chunk_bounding_boxes_from_text_interval(self) -> None:
        use_case = self.build_use_case()
        units = [
            TextUnit(
                text="Edital",
                page=1,
                line_key="1:0:0",
                start_index=0,
                end_index=6,
                x0=10,
                y0=20,
                x1=40,
                y1=30,
            ),
            TextUnit(
                text="matricula",
                page=1,
                line_key="1:0:0",
                start_index=7,
                end_index=16,
                x0=45,
                y0=20,
                x1=90,
                y1=30,
            ),
            TextUnit(
                text="fora",
                page=1,
                line_key="1:0:1",
                start_index=30,
                end_index=34,
                x0=10,
                y0=40,
                x1=30,
                y1=50,
            ),
        ]

        boxes = use_case._build_chunk_bounding_boxes(
            units,
            chunk_start_index=5,
            chunk_end_index=16,
        )

        self.assertEqual(
            boxes,
            [
                {
                    "page": 1,
                    "x0": 10,
                    "y0": 20,
                    "x1": 90,
                    "y1": 30,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
