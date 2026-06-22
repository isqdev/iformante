import asyncio
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

import fitz
import httpx
import tiktoken
from langchain_core.documents import Document

from app.db import build_qdrant_vector_store, upsert_parent_documents


HEADING_PATTERN = re.compile(
    r"^\s*(?:(?:\d+(?:\.\d+)*\.?)|(?:CAP[IÍ]TULO\s+[IVXLCDM]+)|(?:ANEXO\s+[IVXLCDM]+))\s+.+",
    re.IGNORECASE,
)
CHILD_CHUNK_OVERLAP = 64
CHILD_CHUNK_TOKEN_LIMIT = 256
PARENT_CHUNK_MINIMUM = 512
PARENT_CHUNK_TARGET = 768
PARENT_CHUNK_TOKEN_LIMIT = 1024


@dataclass(frozen=True)
class IngestDocumentResult:
    filename: str
    storage_url: str
    chunks_indexed: int


@dataclass(frozen=True)
class StructuredBlock:
    type: str
    page: int
    text: str
    section_path: list[str]
    bbox: list[float]


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    blocks: list[StructuredBlock]


@dataclass(frozen=True)
class ParentChunk:
    parent_id: str
    text: str
    source_text: str
    block_type: str
    pages: list[int]
    section_path: list[str]
    bounding_boxes: list[dict[str, float | int]]


@dataclass(frozen=True)
class ChildChunk:
    child_id: str
    parent_id: str
    text: str
    block_type: str
    pages: list[int]
    section_path: list[str]
    bounding_boxes: list[dict[str, float | int]]


class IngestDocumentUseCase:
    def __init__(
        self,
        openai_api_key: str | None,
        qdrant_url: str | None,
        qdrant_api_key: str | None,
        qdrant_collection: str,
        embedding_model: str,
        embedding_dimensions: int,
        cloudinary_cloud_name: str | None,
        cloudinary_api_key: str | None,
        cloudinary_api_secret: str | None,
        storage_dir: Path | None = None,
    ) -> None:
        self._openai_api_key = openai_api_key
        self._qdrant_url = qdrant_url
        self._qdrant_api_key = qdrant_api_key
        self._qdrant_collection = qdrant_collection
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions
        self._cloudinary_cloud_name = cloudinary_cloud_name
        self._cloudinary_api_key = cloudinary_api_key
        self._cloudinary_api_secret = cloudinary_api_secret
        self._storage_dir = storage_dir or Path(tempfile.gettempdir()) / "iformante"
        self._encoding = self._build_encoding()

    @property
    def is_configured(self) -> bool:
        return bool(
            self._openai_api_key
            and self._qdrant_url
            and self._cloudinary_cloud_name
            and self._cloudinary_api_key
            and self._cloudinary_api_secret
        )

    async def execute(self, url: str, document_id: str | None = None) -> IngestDocumentResult:
        if not self._openai_api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

        if not self._qdrant_url:
            raise RuntimeError("QDRANT_URL nao configurada no back-end.")

        document_path, content_type = await self._download_document(url)
        try:
            extracted_document = self._extract_document(document_path, content_type)

            if not extracted_document.text.strip():
                raise ValueError("Nao foi possivel extrair texto do documento.")

            resolved_document_id = document_id or uuid4().hex
            cloudinary_url = await self._upload_document(
                document_path,
                resolved_document_id,
            )
            created_at = datetime.now(UTC).isoformat()
            parent_chunks = self._build_parent_chunks(extracted_document.blocks)
            child_chunks = self._build_child_chunks(parent_chunks)
            parent_documents = [
                Document(
                    page_content=parent.text,
                    metadata={
                        "parent_id": parent.parent_id,
                        "document_id": resolved_document_id,
                        "title": document_path.name,
                        "filename": document_path.name,
                        "source_url": cloudinary_url,
                        "origin_url": url,
                        "type": parent.block_type,
                        "page": parent.pages[0] if parent.pages else None,
                        "page_numbers": parent.pages,
                        "section_path": parent.section_path,
                        "bbox": parent.bounding_boxes[0] if parent.bounding_boxes else None,
                        "bounding_boxes": parent.bounding_boxes,
                        "parent_index": index,
                        "parent_count": len(parent_chunks),
                        "created_at": created_at,
                        "source_text": parent.source_text,
                    },
                )
                for index, parent in enumerate(parent_chunks)
            ]
            child_documents = [
                Document(
                    page_content=child.text,
                    metadata={
                        "parent_id": child.parent_id,
                        "document_id": resolved_document_id,
                        "title": document_path.name,
                        "filename": document_path.name,
                        "source_url": cloudinary_url,
                        "origin_url": url,
                        "type": child.block_type,
                        "page": child.pages[0] if child.pages else None,
                        "page_numbers": child.pages,
                        "section_path": child.section_path,
                        "bbox": child.bounding_boxes[0] if child.bounding_boxes else None,
                        "bounding_boxes": child.bounding_boxes,
                        "chunk_id": child.child_id,
                        "chunk_index": index,
                        "chunk_count": len(child_chunks),
                        "created_at": created_at,
                    },
                )
                for index, child in enumerate(child_chunks)
            ]

            upsert_parent_documents(parent_documents)
            vector_store = build_qdrant_vector_store()
            vector_store.add_documents(documents=child_documents)

            return IngestDocumentResult(
                filename=document_path.name,
                storage_url=cloudinary_url,
                chunks_indexed=len(child_documents),
            )
        finally:
            shutil.rmtree(document_path.parent, ignore_errors=True)

    async def _download_document(self, url: str) -> tuple[Path, str]:
        parsed_url = urlparse(url)

        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("Informe uma URL HTTP ou HTTPS valida.")

        target_dir = self._storage_dir / uuid4().hex
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / self._build_filename(parsed_url.path)

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    content_type = response.headers.get(
                        "content-type",
                        "application/octet-stream",
                    )

                    with target_path.open("wb") as document_file:
                        async for chunk in response.aiter_bytes():
                            if chunk:
                                document_file.write(chunk)
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        return target_path, content_type

    async def _upload_document(self, document_path: Path, document_id: str) -> str:
        if not (
            self._cloudinary_cloud_name
            and self._cloudinary_api_key
            and self._cloudinary_api_secret
        ):
            raise RuntimeError("Credenciais do Cloudinary nao configuradas no back-end.")

        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=self._cloudinary_cloud_name,
            api_key=self._cloudinary_api_key,
            api_secret=self._cloudinary_api_secret,
            secure=True,
        )
        try:
            upload_result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                str(document_path),
                resource_type="raw",
                folder="iformante/documents",
                public_id=f"{document_id}/{document_path.name}",
                overwrite=True,
            )
        except Exception as error:
            raise RuntimeError(
                "Nao foi possivel enviar o documento para o Cloudinary.",
            ) from error
        secure_url = str(upload_result.get("secure_url") or "").strip()

        if not secure_url:
            raise RuntimeError("O Cloudinary nao retornou a URL segura do documento.")

        return secure_url

    def _extract_document(self, document_path: Path, content_type: str) -> ExtractedDocument:
        with document_path.open("rb") as document_file:
            signature = document_file.read(5)

        if signature != b"%PDF-":
            raise ValueError("Apenas documentos PDF sao aceitos.")

        return self._extract_pdf_document(document_path)

    def _extract_pdf_document(self, document_path: Path) -> ExtractedDocument:
        blocks: list[StructuredBlock] = []
        section_path: list[str] = []

        with fitz.open(document_path) as pdf_document:
            for page_number, page in enumerate(pdf_document, start=1):
                table_bboxes = [table.bbox for table in page.find_tables().tables]
                blocks.extend(
                    self._extract_text_blocks(
                        page,
                        page_number,
                        section_path,
                        table_bboxes,
                    ),
                )
                blocks.extend(self._extract_tables(page, page_number, section_path))

        blocks = sorted(
            blocks,
            key=lambda block: (
                block.page,
                block.bbox[1] if block.bbox else 0,
                block.bbox[0] if block.bbox else 0,
            ),
        )
        text = "\n\n".join(block.text for block in blocks)
        return ExtractedDocument(text=text, blocks=blocks)

    def _extract_text_blocks(
        self,
        page: fitz.Page,
        page_number: int,
        section_path: list[str],
        table_bboxes: list[tuple[float, float, float, float]],
    ) -> list[StructuredBlock]:
        extracted_blocks: list[StructuredBlock] = []
        raw_blocks = page.get_text("dict").get("blocks", [])

        for block in raw_blocks:
            if block.get("type") != 0:
                continue

            bbox = self._round_bbox(block.get("bbox", []))

            if self._is_inside_table(bbox, table_bboxes):
                continue

            text = self._normalize_text(
                " ".join(
                    span.get("text", "")
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                ),
            )

            if not text:
                continue

            block_type = "heading" if self._is_heading(text) else "paragraph"

            if block_type == "heading":
                section_path[:] = self._update_section_path(section_path, text)

            extracted_blocks.append(
                StructuredBlock(
                    type=block_type,
                    page=page_number,
                    text=text,
                    section_path=list(section_path),
                    bbox=bbox,
                ),
            )

        return extracted_blocks

    def _extract_tables(
        self,
        page: fitz.Page,
        page_number: int,
        section_path: list[str],
    ) -> list[StructuredBlock]:
        blocks: list[StructuredBlock] = []
        tables = page.find_tables()

        for table in tables.tables:
            rows = [
                [self._normalize_text(cell or "") for cell in row]
                for row in table.extract()
                if any(self._normalize_text(cell or "") for cell in row)
            ]

            if not rows:
                continue

            blocks.append(
                StructuredBlock(
                    type="table",
                    page=page_number,
                    text=self._table_to_markdown(rows),
                    section_path=list(section_path),
                    bbox=self._round_bbox(table.bbox),
                ),
            )

        return blocks

    def _build_semantic_chunks(self, blocks: list[StructuredBlock]) -> list[ParentChunk]:
        return self._build_parent_chunks(blocks)

    def _build_parent_chunks(self, blocks: list[StructuredBlock]) -> list[ParentChunk]:
        buffers: list[list[StructuredBlock]] = []
        buffer: list[StructuredBlock] = []

        for block in blocks:
            if not buffer:
                buffer = [block]
                continue

            buffer_tokens = self._count_block_tokens(buffer)
            combined_tokens = self._count_block_tokens([*buffer, block])
            starts_new_section = (
                block.type == "heading"
                and block.section_path != buffer[-1].section_path
            )

            if (
                self._can_share_parent(buffer, block)
                and combined_tokens <= PARENT_CHUNK_TOKEN_LIMIT
                and not (
                    buffer_tokens >= PARENT_CHUNK_TARGET
                    and starts_new_section
                )
            ):
                buffer.append(block)
                continue

            buffers.append(buffer)
            buffer = [block]

        if buffer:
            buffers.append(buffer)

        buffers = self._merge_small_parent_buffers(buffers)
        chunks: list[ParentChunk] = []

        for parent_blocks in buffers:
            chunks.extend(self._blocks_to_chunks(parent_blocks))

        return chunks

    def _can_share_parent(
        self,
        current_blocks: list[StructuredBlock],
        next_block: StructuredBlock,
    ) -> bool:
        if next_block.type == "table" or any(
            block.type == "table" for block in current_blocks
        ):
            return False

        return self._section_scope(current_blocks[0]) == self._section_scope(
            next_block,
        )

    def _merge_small_parent_buffers(
        self,
        buffers: list[list[StructuredBlock]],
    ) -> list[list[StructuredBlock]]:
        merged: list[list[StructuredBlock]] = []

        for buffer in buffers:
            if not merged:
                merged.append(buffer)
                continue

            previous = merged[-1]
            combined = [*previous, *buffer]
            can_merge = (
                self._count_block_tokens(combined) <= PARENT_CHUNK_TOKEN_LIMIT
                and self._can_share_parent(previous, buffer[0])
            )
            has_small_side = (
                self._count_block_tokens(previous) < PARENT_CHUNK_MINIMUM
                or self._count_block_tokens(buffer) < PARENT_CHUNK_MINIMUM
            )

            if can_merge and has_small_side:
                merged[-1] = combined
            else:
                merged.append(buffer)

        return merged

    def _section_scope(self, block: StructuredBlock) -> tuple[str, ...]:
        return tuple(block.section_path[:1])

    def _blocks_to_chunks(self, blocks: list[StructuredBlock]) -> list[ParentChunk]:
        body = self._build_chunk_body(blocks)
        section_path = self._most_specific_section_path(blocks)
        heading = section_path[-1] if section_path else ""
        text = self._compose_chunk_text(heading, body)

        if self._count_tokens(text) <= PARENT_CHUNK_TOKEN_LIMIT:
            return [self._create_parent_chunk(blocks, body)]

        if any(block.type == "table" for block in blocks):
            return self._split_table_blocks(blocks)

        return self._split_text_blocks(blocks)

    def _create_semantic_chunk(
        self,
        blocks: list[StructuredBlock],
        body: str,
    ) -> ParentChunk:
        return self._create_parent_chunk(blocks, body)

    def _create_parent_chunk(
        self,
        blocks: list[StructuredBlock],
        body: str,
    ) -> ParentChunk:
        section_path = self._most_specific_section_path(blocks)
        heading = section_path[-1] if section_path else ""
        text = self._compose_chunk_text(heading, body)
        pages = sorted({block.page for block in blocks})
        block_types = {block.type for block in blocks}
        block_type = next(iter(block_types)) if len(block_types) == 1 else "mixed"

        return ParentChunk(
            parent_id=uuid4().hex,
            text=text,
            source_text=body,
            block_type=block_type,
            pages=pages,
            section_path=section_path,
            bounding_boxes=[
                {
                    "page": block.page,
                    "x0": block.bbox[0],
                    "y0": block.bbox[1],
                    "x1": block.bbox[2],
                    "y1": block.bbox[3],
                }
                for block in blocks
                if block.bbox
            ],
        )

    def _split_text_blocks(self, blocks: list[StructuredBlock]) -> list[ParentChunk]:
        section_path = self._most_specific_section_path(blocks)
        heading = section_path[-1] if section_path else ""
        bodies = self._split_content_by_tokens(
            content=self._build_chunk_body(blocks),
            heading=heading,
            token_limit=PARENT_CHUNK_TOKEN_LIMIT,
            overlap=0,
        )
        return [self._create_parent_chunk(blocks, body) for body in bodies]

    def _split_table_blocks(self, blocks: list[StructuredBlock]) -> list[ParentChunk]:
        table_block = next((block for block in blocks if block.type == "table"), None)

        if table_block is None:
            return self._split_text_blocks(blocks)

        lines = table_block.text.splitlines()

        if len(lines) <= 3:
            return self._split_text_blocks(blocks)

        header = lines[:2]
        rows = lines[2:]
        chunks: list[ParentChunk] = []
        current_rows: list[str] = []
        section_path = self._most_specific_section_path(blocks)
        heading = section_path[-1] if section_path else ""

        for row in rows:
            candidate = "\n".join([*header, *current_rows, row])

            if (
                current_rows
                and self._count_tokens(self._compose_chunk_text(heading, candidate))
                > PARENT_CHUNK_TOKEN_LIMIT
            ):
                chunks.append(
                    self._create_parent_chunk(
                        [table_block],
                        "\n".join([*header, *current_rows]),
                    ),
                )
                overlap_rows = self._select_overlap_rows(
                    heading,
                    header,
                    current_rows,
                )
                current_rows = [*overlap_rows, row]
                continue

            current_rows.append(row)

        if current_rows:
            chunks.append(
                self._create_parent_chunk(
                    [table_block],
                    "\n".join([*header, *current_rows]),
                ),
            )

        return chunks

    def _build_child_chunks(self, parent_chunks: list[ParentChunk]) -> list[ChildChunk]:
        children: list[ChildChunk] = []

        for parent in parent_chunks:
            children.extend(self._split_parent_into_children(parent))

        return children

    def _split_parent_into_children(self, parent: ParentChunk) -> list[ChildChunk]:
        heading = parent.section_path[-1] if parent.section_path else ""
        if parent.block_type == "table":
            child_texts = self._split_table_parent_into_children(parent, heading)
        else:
            bodies = self._split_content_by_tokens(
                content=parent.source_text,
                heading=heading,
                token_limit=CHILD_CHUNK_TOKEN_LIMIT,
                overlap=CHILD_CHUNK_OVERLAP,
            )
            child_texts = [
                self._compose_chunk_text(heading, body)
                for body in bodies
            ]

        return [
            ChildChunk(
                child_id=uuid4().hex,
                parent_id=parent.parent_id,
                text=text,
                block_type=parent.block_type,
                pages=parent.pages,
                section_path=parent.section_path,
                bounding_boxes=parent.bounding_boxes,
            )
            for text in child_texts
        ]

    def _split_table_parent_into_children(
        self,
        parent: ParentChunk,
        heading: str,
    ) -> list[str]:
        lines = parent.source_text.splitlines()

        if len(lines) <= 2:
            return [
                self._compose_chunk_text(heading, body)
                for body in self._split_content_by_tokens(
                    content=parent.source_text,
                    heading=heading,
                    token_limit=CHILD_CHUNK_TOKEN_LIMIT,
                    overlap=CHILD_CHUNK_OVERLAP,
                )
            ]

        header = lines[:2]
        rows = lines[2:]
        chunks: list[str] = []
        current_rows: list[str] = []

        for row in rows:
            candidate = "\n".join([*header, *current_rows, row])
            candidate_text = self._compose_chunk_text(heading, candidate)

            if current_rows and self._count_tokens(candidate_text) > CHILD_CHUNK_TOKEN_LIMIT:
                chunks.append(
                    self._compose_chunk_text(
                        heading,
                        "\n".join([*header, *current_rows]),
                    ),
                )
                overlap_rows = self._select_overlap_rows(
                    heading,
                    header,
                    current_rows,
                )
                current_rows = [*overlap_rows, row]
                continue

            current_rows.append(row)

        if current_rows:
            chunks.append(
                self._compose_chunk_text(
                    heading,
                    "\n".join([*header, *current_rows]),
                ),
            )

        if all(
            self._count_tokens(chunk) <= CHILD_CHUNK_TOKEN_LIMIT
            for chunk in chunks
        ):
            return chunks

        return [
            self._compose_chunk_text(heading, body)
            for body in self._split_content_by_tokens(
                content=parent.source_text,
                heading=heading,
                token_limit=CHILD_CHUNK_TOKEN_LIMIT,
                overlap=CHILD_CHUNK_OVERLAP,
            )
        ]

    def _select_overlap_rows(
        self,
        heading: str,
        header: list[str],
        rows: list[str],
    ) -> list[str]:
        selected: list[str] = []

        for row in reversed(rows):
            candidate = self._compose_chunk_text(
                heading,
                "\n".join([*header, row, *selected]),
            )

            if self._count_tokens(candidate) > CHILD_CHUNK_OVERLAP and selected:
                break

            selected.insert(0, row)

        return selected

    def _build_chunk_body(self, blocks: list[StructuredBlock]) -> str:
        section_path = self._most_specific_section_path(blocks)
        immediate_heading = section_path[-1] if section_path else ""
        body_parts = [
            block.text
            for block in blocks
            if not (
                len(blocks) > 1
                and block.type == "heading"
                and block.text == immediate_heading
            )
        ]

        return "\n\n".join(body_parts).strip()

    def _compose_chunk_text(self, heading: str, body: str) -> str:
        if not body.strip():
            return heading

        if not heading:
            return body

        if body == heading or body.startswith(f"{heading}\n"):
            return body

        return f"{heading}\n\n{body}"

    def _split_content_by_tokens(
        self,
        content: str,
        heading: str,
        token_limit: int,
        overlap: int,
    ) -> list[str]:
        prefix = f"{heading}\n\n" if heading else ""
        available_tokens = token_limit - len(self._encoding.encode(prefix))

        if available_tokens <= 0:
            # Preserve the complete semantic origin even when a malformed or
            # unusually verbose heading is larger than the regular chunk budget.
            # In this exceptional case, the limit applies only to the body.
            available_tokens = token_limit

        content_tokens = self._encoding.encode(content)

        if not content_tokens:
            return [""]

        effective_overlap = min(overlap, max(available_tokens - 1, 0))
        chunks: list[str] = []
        start = 0

        while start < len(content_tokens):
            end = min(start + available_tokens, len(content_tokens))
            chunks.append(self._encoding.decode(content_tokens[start:end]))

            if end == len(content_tokens):
                break

            start = end - effective_overlap

        return chunks

    def _most_specific_section_path(self, blocks: list[StructuredBlock]) -> list[str]:
        paths = [block.section_path for block in blocks if block.section_path]

        if not paths:
            return []

        return max(paths, key=len)

    def _table_to_markdown(self, rows: list[list[str]]) -> str:
        width = max(len(row) for row in rows)
        normalized_rows = [row + [""] * (width - len(row)) for row in rows]
        header = normalized_rows[0]
        separator = ["---"] * width
        body = normalized_rows[1:]

        return "\n".join(
            [
                self._format_markdown_row(header),
                self._format_markdown_row(separator),
                *[self._format_markdown_row(row) for row in body],
            ],
        )

    def _format_markdown_row(self, row: list[str]) -> str:
        return "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |"

    def _is_heading(self, text: str) -> bool:
        if HEADING_PATTERN.match(text):
            return True

        return (
            len(text) <= 90
            and text.upper() == text
            and any(character.isalpha() for character in text)
        )

    def _update_section_path(self, current_path: list[str], heading: str) -> list[str]:
        match = re.match(r"^\s*(\d+(?:\.\d+)*)", heading)

        if not match:
            return [heading]

        level = match.group(1).count(".") + 1
        next_path = current_path[: level - 1]
        next_path.append(heading)
        return next_path

    def _is_inside_table(
        self,
        bbox: list[float],
        table_bboxes: list[tuple[float, float, float, float]],
    ) -> bool:
        return any(self._intersection_ratio(bbox, table_bbox) > 0.85 for table_bbox in table_bboxes)

    def _intersection_ratio(
        self,
        bbox: list[float],
        other: tuple[float, float, float, float],
    ) -> float:
        if not bbox:
            return 0

        x0 = max(bbox[0], float(other[0]))
        y0 = max(bbox[1], float(other[1]))
        x1 = min(bbox[2], float(other[2]))
        y1 = min(bbox[3], float(other[3]))

        if x1 <= x0 or y1 <= y0:
            return 0

        intersection = (x1 - x0) * (y1 - y0)
        area = max((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 1)
        return intersection / area

    def _count_block_tokens(self, blocks: list[StructuredBlock]) -> int:
        section_path = self._most_specific_section_path(blocks)
        heading = section_path[-1] if section_path else ""
        return self._count_tokens(
            self._compose_chunk_text(heading, self._build_chunk_body(blocks)),
        )

    def _count_tokens(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def _build_encoding(self):
        try:
            return tiktoken.encoding_for_model(self._embedding_model)
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _round_bbox(self, bbox: list[float] | tuple[float, ...]) -> list[float]:
        return [round(float(value), 2) for value in bbox]

    def _build_filename(self, url_path: str) -> str:
        original_name = Path(unquote(url_path)).name

        if not original_name:
            return f"document-{uuid4().hex}"

        return re.sub(r'[<>:"/\\|?*]', "_", original_name).strip() or f"document-{uuid4().hex}"
