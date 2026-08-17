import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from qdrant_client.models import Filter

from app.app import app
from app.routes.document import (
    get_delete_document_use_case,
    get_ingest_document_use_case,
)
from app.use_cases.documents.delete_document import DeleteDocumentUseCase
from app.rag.ingestion import (
    CHILD_CHUNK_OVERLAP,
    CHILD_CHUNK_TOKEN_LIMIT,
    PARENT_CHUNK_TOKEN_LIMIT,
    DocumentIngestor,
    ParentChunk,
    IngestDocumentResult,
    StructuredBlock,
)


class FakeIngestDocumentUseCase:
    async def execute(self, url: str) -> IngestDocumentResult:
        return IngestDocumentResult(
            filename="document-test.pdf",
            storage_url="https://res.cloudinary.com/example/raw/upload/document-test.pdf",
            chunks_indexed=3,
        )


class FakeDeleteDocumentUseCase:
    async def execute(self, document_id: str):
        self.document_id = document_id

        class Result:
            document_id = "doc123456"

        return Result()


class FakeStreamResponse:
    status_code = 200
    url = "https://example.com/document.pdf"
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
        app.dependency_overrides[get_delete_document_use_case] = FakeDeleteDocumentUseCase
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
        self.assertEqual(
            response.json()["path"],
            "https://res.cloudinary.com/example/raw/upload/document-test.pdf",
        )
        self.assertEqual(response.json()["chunks_indexed"], 3)

    def test_download_document_rejects_empty_url(self) -> None:
        response = self.client.post("/documents/download", json={"url": ""})

        self.assertEqual(response.status_code, 422)

    def test_delete_document_returns_deleted_document_id(self) -> None:
        response = self.client.delete("/documents/doc123456")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "document_id": "doc123456",
                "deleted": True,
            },
        )


class FakeQdrantClient:
    def __init__(self) -> None:
        self.deleted_calls = []

    def collection_exists(self, collection_name):
        return True

    def delete(self, collection_name, points_selector, wait):
        self.deleted_calls.append(
            {
                "collection_name": collection_name,
                "points_selector": points_selector,
                "wait": wait,
            },
        )


class FakeDeletionDocument:
    id = "doc123456"
    file_name = "document.pdf"


class FakeDeletionDocumentRepository:
    async def get_by_id(self, document_id):
        return FakeDeletionDocument()

    async def delete(self, document):
        self.deleted_document = document


class FakeUnitOfWork:
    async def commit(self):
        self.committed = True


class DocumentIngestorTests(unittest.IsolatedAsyncioTestCase):
    def build_use_case(self, storage_dir: Path | None = None) -> DocumentIngestor:
        return DocumentIngestor(
            openai_api_key="test-key",
            qdrant_url="https://qdrant.example",
            qdrant_api_key="test-qdrant-key",
            qdrant_collection="my-collection",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=1536,
            cloudinary_cloud_name="test-cloud",
            cloudinary_api_key="test-key",
            cloudinary_api_secret="test-secret",
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

    async def test_download_uses_original_filename_from_url(self) -> None:
        with TemporaryDirectory() as temp_dir:
            use_case = self.build_use_case(storage_dir=Path(temp_dir))

            with patch("httpx.AsyncClient.stream", return_value=FakeStreamContext()):
                path, _ = await use_case._download_document(
                    "https://example.com/docs/Edital%20Integrado.pdf",
                )

            self.assertEqual(path.name, "Edital Integrado.pdf")

    async def test_rejects_non_pdf_document(self) -> None:
        use_case = self.build_use_case()

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "arquivo.pdf"
            path.write_text("nao e um pdf", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Apenas documentos PDF"):
                use_case._extract_document(path, "application/pdf")

    async def test_merges_small_blocks_from_same_section(self) -> None:
        use_case = self.build_use_case()
        blocks = [
            StructuredBlock(
                type="heading",
                page=1,
                text="3.2 Cotas",
                section_path=["3 Cursos", "3.2 Cotas"],
                bbox=[10, 20, 40, 30],
            ),
            StructuredBlock(
                type="paragraph",
                page=1,
                text="Primeira parte da regra.",
                section_path=["3 Cursos", "3.2 Cotas"],
                bbox=[10, 40, 90, 50],
            ),
            StructuredBlock(
                type="paragraph",
                page=1,
                text="Segunda parte da regra.",
                section_path=["3 Cursos", "3.2 Cotas"],
                bbox=[10, 60, 90, 70],
            ),
        ]

        chunks = use_case._build_semantic_chunks(blocks)

        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].text.startswith("3.2 Cotas\n\n"))
        self.assertIn("Primeira parte da regra.", chunks[0].text)
        self.assertIn("Segunda parte da regra.", chunks[0].text)
        self.assertEqual(chunks[0].section_path, ["3 Cursos", "3.2 Cotas"])
        self.assertEqual(len(chunks[0].bounding_boxes), 3)

    async def test_splits_large_table_and_repeats_header(self) -> None:
        use_case = self.build_use_case()
        rows = ["| Curso | Vagas |", "| --- | --- |"]
        rows.extend(f"| Curso {index} | {'texto ' * 80} |" for index in range(20))
        blocks = [
            StructuredBlock(
                type="table",
                page=2,
                text="\n".join(rows),
                section_path=["3 Cursos", "3.2 Vagas"],
                bbox=[10, 20, 500, 700],
            ),
        ]

        chunks = use_case._build_semantic_chunks(blocks)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertIn("| Curso | Vagas |", chunk.text)
            self.assertIn("| --- | --- |", chunk.text)
            self.assertLessEqual(
                use_case._count_tokens(chunk.text),
                PARENT_CHUNK_TOKEN_LIMIT,
            )

    async def test_groups_adjacent_subsections_into_larger_parents(self) -> None:
        use_case = self.build_use_case()
        blocks: list[StructuredBlock] = []

        for index in range(1, 6):
            section_path = ["4 Acoes afirmativas", f"4.{index} Regra {index}"]
            blocks.extend(
                [
                    StructuredBlock(
                        type="heading",
                        page=index,
                        text=section_path[-1],
                        section_path=section_path,
                        bbox=[10, 20, 200, 30],
                    ),
                    StructuredBlock(
                        type="paragraph",
                        page=index,
                        text="regra institucional aplicavel " * 70,
                        section_path=section_path,
                        bbox=[10, 40, 500, 100],
                    ),
                ],
            )

        parents = use_case._build_parent_chunks(blocks)
        token_counts = [use_case._count_tokens(parent.text) for parent in parents]

        self.assertTrue(all(count <= PARENT_CHUNK_TOKEN_LIMIT for count in token_counts))
        self.assertTrue(any(count >= 512 for count in token_counts))

    async def test_splits_children_with_real_token_limits_and_overlap(self) -> None:
        use_case = self.build_use_case()
        content = " ".join(f"termo{index}" for index in range(500))
        parent = ParentChunk(
            parent_id="parent-1",
            text=content,
            source_text=content,
            block_type="paragraph",
            pages=[1],
            section_path=[],
            bounding_boxes=[],
        )

        children = use_case._split_parent_into_children(parent)

        self.assertGreater(len(children), 1)
        self.assertTrue(
            all(
                use_case._count_tokens(child.text) <= CHILD_CHUNK_TOKEN_LIMIT
                for child in children
            ),
        )
        first_tokens = use_case._encoding.encode(children[0].text)
        second_tokens = use_case._encoding.encode(children[1].text)
        self.assertEqual(
            first_tokens[-CHILD_CHUNK_OVERLAP:],
            second_tokens[:CHILD_CHUNK_OVERLAP],
        )

    async def test_child_is_not_parent_copy_when_parent_exceeds_limit(self) -> None:
        use_case = self.build_use_case()
        content = "regulamento institucional " * 220
        parent = ParentChunk(
            parent_id="parent-1",
            text=content,
            source_text=content,
            block_type="paragraph",
            pages=[1],
            section_path=[],
            bounding_boxes=[],
        )

        self.assertGreater(
            use_case._count_tokens(parent.text),
            CHILD_CHUNK_TOKEN_LIMIT,
        )
        children = use_case._split_parent_into_children(parent)

        self.assertGreater(len(children), 1)
        self.assertTrue(all(child.text != parent.text for child in children))

    async def test_preserves_heading_larger_than_child_token_limit(self) -> None:
        use_case = self.build_use_case()
        heading = "3.2.1 " + "regra institucional extensa " * 140
        content = "conteudo aplicavel ao estudante " * 80
        parent = ParentChunk(
            parent_id="parent-long-heading",
            text=f"{heading}\n\n{content}",
            source_text=content,
            block_type="paragraph",
            pages=[2],
            section_path=["3 Cursos e vagas", heading],
            bounding_boxes=[],
        )

        children = use_case._split_parent_into_children(parent)

        self.assertGreater(len(children), 1)
        self.assertTrue(
            all(child.text.startswith(f"{heading}\n\n") for child in children),
        )
        self.assertTrue(
            all(child.section_path[-1] == heading for child in children),
        )

    async def test_table_children_preserve_markdown_header(self) -> None:
        use_case = self.build_use_case()
        rows = ["| Curso | Vagas |", "| --- | --- |"]
        rows.extend(f"| Curso {index} | {'descricao ' * 25} |" for index in range(12))
        parent = ParentChunk(
            parent_id="parent-table",
            text="\n".join(rows),
            source_text="\n".join(rows),
            block_type="table",
            pages=[2],
            section_path=["3 Cursos", "3.2 Vagas"],
            bounding_boxes=[],
        )

        children = use_case._split_parent_into_children(parent)

        self.assertGreater(len(children), 1)
        self.assertTrue(
            all("| Curso | Vagas |" in child.text for child in children),
        )
        self.assertTrue(
            all("| --- | --- |" in child.text for child in children),
        )
        self.assertTrue(
            all(
                use_case._count_tokens(child.text) <= CHILD_CHUNK_TOKEN_LIMIT
                for child in children
            ),
        )


class DeleteDocumentUseCaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_deletes_qdrant_points_by_document_id_metadata(self) -> None:
        qdrant_client = FakeQdrantClient()
        use_case = DeleteDocumentUseCase(
            qdrant_url="https://qdrant.example",
            qdrant_collection="my-collection",
            document_repository=FakeDeletionDocumentRepository(),
            unit_of_work=FakeUnitOfWork(),
            cloudinary_cloud_name="test-cloud",
            cloudinary_api_key="test-key",
            cloudinary_api_secret="test-secret",
            qdrant_client=qdrant_client,
        )

        with patch.object(use_case, "_delete_from_cloudinary", new=AsyncMock()):
            result = await use_case.execute(" doc123456 ")
        child_delete = qdrant_client.deleted_calls[0]
        parent_delete = qdrant_client.deleted_calls[1]
        points_selector = child_delete["points_selector"]

        self.assertEqual(result.document_id, "doc123456")
        self.assertEqual(child_delete["collection_name"], "my-collection")
        self.assertEqual(parent_delete["collection_name"], "my-collection-parents")
        self.assertTrue(child_delete["wait"])
        self.assertTrue(parent_delete["wait"])
        self.assertIsInstance(points_selector.filter, Filter)
        self.assertEqual(points_selector.filter.must[0].key, "metadata.document_id")
        self.assertEqual(points_selector.filter.must[0].match.value, "doc123456")
        self.assertEqual(
            parent_delete["points_selector"].filter.must[0].key,
            "document_id",
        )

    async def test_rejects_empty_document_id(self) -> None:
        use_case = DeleteDocumentUseCase(
            qdrant_url="https://qdrant.example",
            qdrant_collection="my-collection",
            document_repository=FakeDeletionDocumentRepository(),
            unit_of_work=FakeUnitOfWork(),
            cloudinary_cloud_name="test-cloud",
            cloudinary_api_key="test-key",
            cloudinary_api_secret="test-secret",
            qdrant_client=FakeQdrantClient(),
        )

        with self.assertRaises(ValueError):
            await use_case.execute(" ")


if __name__ == "__main__":
    unittest.main()
