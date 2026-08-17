import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.rag.ingestion import IngestDocumentResult
from app.use_cases.documents import IngestDocumentUseCase, ListDocumentsUseCase


class DocumentUseCaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_lists_documents_from_repository(self) -> None:
        documents = [SimpleNamespace(id="document-1")]
        repository = SimpleNamespace(list_all=AsyncMock(return_value=documents))
        use_case = ListDocumentsUseCase(repository)

        result = await use_case.execute()

        self.assertEqual(result, documents)
        repository.list_all.assert_awaited_once_with()

    async def test_ingests_and_marks_document_as_indexed(self) -> None:
        async def create_document(document):
            document.id = "document1"
            return document

        repository = SimpleNamespace(
            create=AsyncMock(side_effect=create_document),
        )
        unit_of_work = SimpleNamespace(commit=AsyncMock())
        downloaded = SimpleNamespace(
            filename="document.pdf",
            path=SimpleNamespace(),
        )
        storage = SimpleNamespace(
            download_pdf=AsyncMock(return_value=downloaded),
        )
        result = IngestDocumentResult(
            filename="document.pdf",
            storage_url="https://storage.example/document.pdf",
            chunks_indexed=3,
        )
        ingestor = SimpleNamespace(execute=AsyncMock(return_value=result))
        use_case = IngestDocumentUseCase(
            repository=repository,
            unit_of_work=unit_of_work,
            document_storage=storage,
            document_ingestor=ingestor,
        )

        actual_result = await use_case.execute("https://example.com/document.pdf")

        document = repository.create.await_args.args[0]
        self.assertEqual(actual_result, result)
        self.assertEqual(document.file_name, "document.pdf")
        self.assertEqual(document.total_chunks, 3)
        self.assertEqual(document.ingestion_status, "INDEXED")
        ingestor.execute.assert_awaited_once_with(
            downloaded.path,
            document_id="document1",
            filename="document.pdf",
        )
        storage.download_pdf.assert_awaited_once_with(
            "https://example.com/document.pdf",
            "document1",
        )
        self.assertEqual(unit_of_work.commit.await_count, 2)
