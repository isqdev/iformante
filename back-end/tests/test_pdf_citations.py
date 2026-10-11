import tempfile
import unittest
from pathlib import Path
import fitz
from app.services.pdf_anchors import chunk_anchors
from app.services.citations import group_citations


class PdfCitationTests(unittest.TestCase):
    def test_highlights_only_matching_text_and_handles_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.pdf"
            pdf = fitz.open()
            page = pdf.new_page()
            page.insert_text((60, 100), "Este trecho pertence ao chunk utilizado.")
            page.insert_text((60, 140), "Este outro trecho deve permanecer sem destaque.")
            page.set_rotation(90)
            pdf.save(path)
            pdf.close()
            anchors = chunk_anchors(path, 1, "Este trecho pertence ao chunk utilizado.")
            self.assertEqual(len(anchors), 1)
            for field in ["x", "y", "width", "height"]:
                self.assertGreaterEqual(anchors[0][field], 0)
                self.assertLessEqual(anchors[0][field], 1)
            self.assertLess(anchors[0]["width"], .1)

    def test_preserves_every_chunk_and_separates_documents(self):
        items = [{"document_id": doc, "filename": doc, "url": None, "source_type": "PDF", "chunk_id": chunk, "bbox": [{"page": page}]} for doc, chunk, page in [("A", "one", 1), ("A", "two", 3), ("B", "three", 1), ("A", "one", 1)]]
        result = group_citations(items)
        self.assertEqual(len(result), 2)
        self.assertEqual([c["chunk_id"] for c in result[0]["citations"]], ["one", "two"])
        self.assertEqual(result[1]["citations"][0]["chunk_id"], "three")

    def test_partial_lines_and_short_table_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "table.pdf"
            pdf = fitz.open()
            page = pdf.new_page()
            page.insert_text((60, 100), "Antes do trecho as palavras utilizadas depois do trecho")
            page.insert_text((60, 140), "2026 120 300")
            pdf.save(path)
            pdf.close()
            anchors = chunk_anchors(path, 1, "as palavras utilizadas")
            self.assertEqual(len(anchors), 1)
            self.assertGreater(anchors[0]["x"], .2)
            anchors = chunk_anchors(path, 1, "| 2026 | 120 | 300 |")
            self.assertEqual(len(anchors), 1)
            self.assertIn("width", anchors[0])

if __name__ == "__main__": unittest.main()
