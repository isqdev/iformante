import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

import fitz
import httpx
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.db import build_qdrant_vector_store


@dataclass(frozen=True)
class IngestDocumentResult:
    filename: str
    path: Path
    chunks_indexed: int


@dataclass(frozen=True)
class TextUnit:
    text: str
    page: int
    line_key: str
    start_index: int
    end_index: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    units: list[TextUnit]


class IngestDocumentUseCase:
    def __init__(
        self,
        openai_api_key: str | None,
        qdrant_url: str | None,
        qdrant_api_key: str | None,
        qdrant_collection: str,
        embedding_model: str,
        embedding_dimensions: int,
        storage_dir: Path | None = None,
    ) -> None:
        self._openai_api_key = openai_api_key
        self._qdrant_url = qdrant_url
        self._qdrant_api_key = qdrant_api_key
        self._qdrant_collection = qdrant_collection
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions
        self._storage_dir = storage_dir or Path(__file__).resolve().parents[2] / "downloads"

    @property
    def is_configured(self) -> bool:
        return bool(self._openai_api_key and self._qdrant_url)

    async def execute(self, url: str, document_id: str | None = None) -> IngestDocumentResult:
        if not self._openai_api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

        if not self._qdrant_url:
            raise RuntimeError("QDRANT_URL nao configurada no back-end.")

        document_path, content_type = await self._download_document(url)
        extracted_document = self._extract_document(document_path, content_type)

        if not extracted_document.text.strip():
            raise ValueError("Nao foi possivel extrair texto do documento.")

        resolved_document_id = document_id or uuid4().hex
        created_at = datetime.now(UTC).isoformat()
        base_document = Document(
            page_content=extracted_document.text,
            metadata={
                "source_url": url,
                "filename": document_path.name,
                "document_id": resolved_document_id,
                "content_type": content_type,
                "created_at": created_at,
            },
        )
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True,
        )
        chunks = text_splitter.split_documents([base_document])

        for index, chunk in enumerate(chunks):
            start_index = int(chunk.metadata.get("start_index", 0))
            end_index = start_index + len(chunk.page_content)
            bounding_boxes = self._build_chunk_bounding_boxes(
                extracted_document.units,
                start_index,
                end_index,
            )
            page_numbers = sorted({box["page"] for box in bounding_boxes})

            chunk.metadata.update(
                {
                    "chunk_id": uuid4().hex,
                    "chunk_index": index,
                    "chunk_count": len(chunks),
                    "start_index": start_index,
                    "end_index": end_index,
                    "page_numbers": page_numbers,
                    "bounding_boxes": bounding_boxes,
                },
            )

        vector_store = build_qdrant_vector_store()
        vector_store.add_documents(documents=chunks)

        return IngestDocumentResult(
            filename=document_path.name,
            path=document_path,
            chunks_indexed=len(chunks),
        )

    async def _download_document(self, url: str) -> tuple[Path, str]:
        parsed_url = urlparse(url)

        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("Informe uma URL HTTP ou HTTPS valida.")

        self._storage_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._storage_dir / self._build_filename(parsed_url.path)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "application/octet-stream")

                with target_path.open("wb") as document_file:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            document_file.write(chunk)

        return target_path, content_type

    def _extract_document(self, document_path: Path, content_type: str) -> ExtractedDocument:
        if document_path.suffix.lower() == ".pdf" or "pdf" in content_type:
            return self._extract_pdf_document(document_path)

        raw_text = document_path.read_text(encoding="utf-8", errors="ignore")

        if "html" in content_type or document_path.suffix.lower() in {".html", ".htm"}:
            raw_text = re.sub(r"<script[\s\S]*?</script>", " ", raw_text)
            raw_text = re.sub(r"<style[\s\S]*?</style>", " ", raw_text)
            raw_text = re.sub(r"<[^>]+>", " ", raw_text)

        return ExtractedDocument(text=re.sub(r"\s+", " ", raw_text).strip(), units=[])

    def _extract_pdf_document(self, document_path: Path) -> ExtractedDocument:
        text_parts: list[str] = []
        units: list[TextUnit] = []
        cursor = 0

        with fitz.open(document_path) as pdf_document:
            for page_index, page in enumerate(pdf_document, start=1):
                if text_parts:
                    text_parts.append("\n\n")
                    cursor += 2

                words = page.get_text("words", sort=True)
                previous_line_key: str | None = None

                for word in words:
                    x0, y0, x1, y1, text, block_number, line_number, _ = word
                    line_key = f"{page_index}:{block_number}:{line_number}"

                    if previous_line_key is None:
                        separator = ""
                    elif previous_line_key == line_key:
                        separator = " "
                    else:
                        separator = "\n"

                    if separator:
                        text_parts.append(separator)
                        cursor += len(separator)

                    start_index = cursor
                    text_parts.append(text)
                    cursor += len(text)

                    units.append(
                        TextUnit(
                            text=text,
                            page=page_index,
                            line_key=line_key,
                            start_index=start_index,
                            end_index=cursor,
                            x0=float(x0),
                            y0=float(y0),
                            x1=float(x1),
                            y1=float(y1),
                        ),
                    )
                    previous_line_key = line_key

        return ExtractedDocument(text="".join(text_parts).strip(), units=units)

    def _build_chunk_bounding_boxes(
        self,
        units: list[TextUnit],
        chunk_start_index: int,
        chunk_end_index: int,
    ) -> list[dict[str, float | int]]:
        boxes_by_line: dict[tuple[int, str], dict[str, float | int]] = {}

        for unit in units:
            if chunk_start_index > unit.end_index or chunk_end_index < unit.start_index:
                continue

            key = (unit.page, unit.line_key)
            if key not in boxes_by_line:
                boxes_by_line[key] = {
                    "page": unit.page,
                    "x0": unit.x0,
                    "y0": unit.y0,
                    "x1": unit.x1,
                    "y1": unit.y1,
                }
                continue

            box = boxes_by_line[key]
            box["x0"] = min(float(box["x0"]), unit.x0)
            box["y0"] = min(float(box["y0"]), unit.y0)
            box["x1"] = max(float(box["x1"]), unit.x1)
            box["y1"] = max(float(box["y1"]), unit.y1)

        return sorted(
            boxes_by_line.values(),
            key=lambda box: (
                int(box["page"]),
                float(box["y0"]),
                float(box["x0"]),
            ),
        )

    def _build_filename(self, url_path: str) -> str:
        original_name = Path(unquote(url_path)).name
        suffix = Path(original_name).suffix if original_name else ""

        return f"document-{uuid4().hex}{suffix}"
