import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from app.rag.ingestion.document_ingestor import (
    CHILD_LIMIT,
    PARENT_LIMIT,
    DocumentIngestor,
)
from app.services import DocumentStorage


class DocumentIngestionPipelineTests(unittest.TestCase):
    def build_ingestor(self, root: Path) -> DocumentIngestor:
        return DocumentIngestor(
            api_key="test-key",
            embedding_model="text-embedding-3-small",
            document_storage=DocumentStorage(root),
            rag_repository=SimpleNamespace(),
        )

    def test_removes_page_numbers_and_omitted_images(self) -> None:
        with TemporaryDirectory() as temporary:
            ingestor = self.build_ingestor(Path(temporary))
            cleaned = ingestor._clean_page_text(
                "Cabeçalho\n\nConteúdo útil.\n\n"
                "**==> picture [472 x 55] intentionally omitted <==**\n\n138",
            )

        self.assertIn("Conteúdo útil.", cleaned)
        self.assertNotIn("omitted", cleaned)
        self.assertNotIn("138", cleaned)

    def test_preserves_numeric_table_values(self) -> None:
        with TemporaryDirectory() as temporary:
            ingestor = self.build_ingestor(Path(temporary))
            cleaned = ingestor._clean_page_text(
                "| Item | Quantidade |\n| --- | ---: |\n| Vagas | 138 |",
            )

        self.assertIn("| Vagas | 138 |", cleaned)

    def test_repairs_table_continuation_after_page_break(self) -> None:
        with TemporaryDirectory() as temporary:
            ingestor = self.build_ingestor(Path(temporary))
            pages = [
                {
                    "text": (
                        "| Campus | Curso | Vagas |\n"
                        "| --- | --- | --- |\n"
                        "| ARAPONGAS | Energias Renováveis | 40 |"
                    ),
                    "metadata": {"page": 0},
                },
                {
                    "text": (
                        "| BARRACÃO | Administração | 40 |\n"
                        "| --- | --- | --- |\n"
                        "| CAMPO LARGO | Agroecologia | 40 |"
                    ),
                    "metadata": {"page": 1},
                },
            ]

            cleaned = ingestor._clean_pages(pages)

        second_page = cleaned[1]["text"]
        self.assertTrue(second_page.startswith("| Campus | Curso | Vagas |"))
        self.assertIn(
            "| --- | --- | --- |\n| BARRACÃO | Administração | 40 |",
            second_page,
        )
        self.assertIn("| CAMPO LARGO | Agroecologia | 40 |", second_page)

    def test_table_parents_and_children_repeat_context_and_header(self) -> None:
        with TemporaryDirectory() as temporary:
            ingestor = self.build_ingestor(Path(temporary))
            rows = ["| Curso | Descrição |", "| --- | --- |"]
            rows.extend(
                f"| Curso {index} | {'conteúdo acadêmico ' * 35} |"
                for index in range(30)
            )
            parents = ingestor._split_table(
                "\n".join(rows),
                PARENT_LIMIT,
                "Contexto: Cursos > Matriz",
            )
            self.assertGreater(len(parents), 1)
            self.assertTrue(
                all(ingestor._parent_splitter._length_function(item) <= PARENT_LIMIT for item in parents),
            )

            children = [
                child
                for parent in parents
                for child in ingestor._split_table(
                    parent,
                    CHILD_LIMIT,
                    "",
                    minimum=128,
                )
            ]

        self.assertGreater(len(children), len(parents))
        for chunk in [*parents, *children]:
            self.assertIn("Contexto: Cursos > Matriz", chunk)
            self.assertIn("| Curso | Descrição |", chunk)
            self.assertIn("| --- | --- |", chunk)

    def test_persists_extracted_and_indexed_markdown(self) -> None:
        with TemporaryDirectory() as temporary:
            storage = DocumentStorage(Path(temporary))
            extracted, indexed = storage.persist_markdown(
                "doc123456",
                "original",
                "limpo",
            )

            self.assertEqual(extracted.read_text(encoding="utf-8"), "original")
            self.assertEqual(indexed.read_text(encoding="utf-8"), "limpo")
