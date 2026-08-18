import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf4llm
import tiktoken
from langchain_core.documents import Document as LangChainDocument
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.models import RagDocumentChild, RagDocumentParent, generate_id
from app.repositories import RagRepository
from app.services import DocumentStorage

PARENT_LIMIT = 1024
CHILD_MIN = 128
CHILD_LIMIT = 256
CHILD_OVERLAP = 64
EMBEDDING_BATCH_SIZE = 512
HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
ATOMIC_BLOCK = re.compile(
    r"(?P<image>!\[[^\]]*\]\([^)]*\))|"
    r"(?P<code>```[\s\S]*?```)|"
    r"(?P<table>(?:^\s*\|.*\|\s*$\n?){2,})",
    re.MULTILINE,
)
OMITTED_IMAGE_LINE = re.compile(
    r"^\s*(?:\*{0,2})?(?:==>\s*)?(?:\[?\s*)?"
    r"(?:picture|image)(?:\s*\[[^\]]+\])?\s+"
    r"(?:intentionally\s+)?omitted"
    r"(?:\s*\]|\s*<==)?(?:\*{0,2})?\s*$",
    re.IGNORECASE,
)
PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:p[aá]gina\s+)?\d+(?:\s*(?:/|de)\s*\d+)?\s*$",
    re.IGNORECASE,
)
TABLE_SEPARATOR = re.compile(
    r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$",
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestDocumentResult:
    filename: str
    storage_url: str
    chunks_indexed: int


class DocumentIngestor:
    def __init__(
        self,
        api_key: str | None,
        embedding_model: str,
        document_storage: DocumentStorage,
        rag_repository: RagRepository,
    ) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

        self._document_storage = document_storage
        self._rag_repository = rag_repository
        self._encoding = tiktoken.encoding_for_model(embedding_model)
        self._embeddings = OpenAIEmbeddings(
            api_key=api_key,
            model=embedding_model,
            chunk_size=EMBEDDING_BATCH_SIZE,
        )
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADERS,
            strip_headers=False,
        )
        self._parent_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name=embedding_model,
            chunk_size=PARENT_LIMIT,
            chunk_overlap=0,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self._child_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name=embedding_model,
            chunk_size=CHILD_LIMIT,
            chunk_overlap=CHILD_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    async def execute(
        self,
        pdf_path: Path,
        document_id: str,
        filename: str,
    ) -> IngestDocumentResult:
        logger.info("Iniciando ingestao do documento %s", document_id)

        logger.info("Extraindo Markdown do documento %s", document_id)
        pages = await asyncio.to_thread(
            pymupdf4llm.to_markdown,
            str(pdf_path),
            page_chunks=True,
            header=False,
            footer=False,
        )
        extracted_markdown = self._join_page_markdown(pages)
        cleaned_pages = self._clean_pages(pages)
        indexed_markdown = self._join_page_markdown(cleaned_pages)
        await asyncio.to_thread(
            self._document_storage.persist_markdown,
            document_id,
            extracted_markdown,
            indexed_markdown,
        )
        parents_documents, children_documents = await asyncio.to_thread(
            self._prepare_chunks,
            cleaned_pages,
        )
        if not children_documents:
            raise ValueError("O PDF nao possui conteudo textual que possa ser indexado.")

        logger.info(
            "Gerando embeddings para %s children do documento %s",
            len(children_documents),
            document_id,
        )
        vectors = await self._embeddings.aembed_documents(
            [child.page_content for child in children_documents],
        )

        parents = [
            RagDocumentParent(
                id=parent.metadata["parent_id"],
                document_id=document_id,
                content=parent.page_content,
                bbox=[{"page": parent.metadata["page"]}],
                chunk_index=index,
                token_count=self._parent_splitter._length_function(parent.page_content),
            )
            for index, parent in enumerate(parents_documents)
        ]
        child_indexes: dict[str, int] = {}
        children: list[RagDocumentChild] = []
        for child, vector in zip(children_documents, vectors, strict=True):
            parent_id = child.metadata["parent_id"]
            chunk_index = child_indexes.get(parent_id, 0)
            child_indexes[parent_id] = chunk_index + 1
            children.append(
                RagDocumentChild(
                    id=generate_id(),
                    parent_id=parent_id,
                    content=child.page_content,
                    embedding=vector,
                    chunk_index=chunk_index,
                    token_count=self._child_splitter._length_function(child.page_content),
                )
            )

        await self._rag_repository.replace_document_chunks(document_id, parents, children)
        logger.info("Documento %s indexado com %s children", document_id, len(children))
        return IngestDocumentResult(
            filename=filename,
            storage_url=str(pdf_path),
            chunks_indexed=len(children),
        )

    async def execute_markdown(
        self,
        markdown: str,
        document_id: str,
        filename: str,
        storage_path: Path,
    ) -> IngestDocumentResult:
        """Indexa Markdown de uma pagina web sem passar pelo extrator de PDF."""
        pages = [{"text": markdown, "metadata": {"page": 0}}]
        await asyncio.to_thread(
            self._document_storage.persist_markdown,
            document_id,
            markdown,
            markdown,
        )
        parents_documents, children_documents = await asyncio.to_thread(
            self._prepare_chunks,
            pages,
        )
        if not children_documents:
            raise ValueError("A pagina nao possui conteudo textual para indexar.")

        vectors = await self._embeddings.aembed_documents(
            [child.page_content for child in children_documents],
        )
        parents = [
            RagDocumentParent(
                id=parent.metadata["parent_id"],
                document_id=document_id,
                content=parent.page_content,
                bbox=[],
                chunk_index=index,
                token_count=self._parent_splitter._length_function(parent.page_content),
            )
            for index, parent in enumerate(parents_documents)
        ]
        child_indexes: dict[str, int] = {}
        children: list[RagDocumentChild] = []
        for child, vector in zip(children_documents, vectors, strict=True):
            parent_id = child.metadata["parent_id"]
            chunk_index = child_indexes.get(parent_id, 0)
            child_indexes[parent_id] = chunk_index + 1
            children.append(
                RagDocumentChild(
                    id=generate_id(),
                    parent_id=parent_id,
                    content=child.page_content,
                    embedding=vector,
                    chunk_index=chunk_index,
                    token_count=self._child_splitter._length_function(child.page_content),
                )
            )
        await self._rag_repository.replace_document_chunks(document_id, parents, children)
        return IngestDocumentResult(
            filename=filename,
            storage_url=str(storage_path),
            chunks_indexed=len(children),
        )

    def _prepare_chunks(
        self,
        pages: object,
    ) -> tuple[list[LangChainDocument], list[LangChainDocument]]:
        page_documents = self._to_page_documents(pages)
        parents = self._build_parent_documents(page_documents)
        return parents, self._build_child_documents(parents)

    def _to_page_documents(self, pages: object) -> list[LangChainDocument]:
        documents: list[LangChainDocument] = []
        if not isinstance(pages, list):
            return documents
        for index, item in enumerate(pages):
            text = str(item.get("text", "")) if isinstance(item, dict) else str(item)
            if not text.strip():
                continue
            metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
            page = int(metadata.get("page", index)) + 1
            documents.append(LangChainDocument(page_content=text, metadata={"page": page}))
        return documents

    def _join_page_markdown(self, pages: object) -> str:
        if not isinstance(pages, list):
            return str(pages)
        texts = [
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in pages
        ]
        return "\n\n<!-- page break -->\n\n".join(
            text.strip() for text in texts if text.strip()
        )

    def _clean_pages(self, pages: object) -> object:
        if not isinstance(pages, list):
            return pages
        cleaned: list[object] = []
        for index, item in enumerate(pages):
            if not isinstance(item, dict):
                text = self._clean_page_text(str(item))
                if text:
                    cleaned.append(text)
                continue
            copy = dict(item)
            copy["text"] = self._clean_page_text(str(item.get("text", "")))
            if copy["text"].strip():
                cleaned.append(copy)
        return self._repair_table_continuations(cleaned)

    def _clean_page_text(self, text: str) -> str:
        lines = text.splitlines()
        non_empty = [index for index, line in enumerate(lines) if line.strip()]
        edge_indexes = set(non_empty[:3] + non_empty[-3:])
        cleaned: list[str] = []
        for index, line in enumerate(lines):
            stripped = line.strip()
            if OMITTED_IMAGE_LINE.fullmatch(stripped):
                continue
            if (
                index in edge_indexes
                and not stripped.startswith("|")
                and PAGE_NUMBER_LINE.fullmatch(stripped)
            ):
                continue
            cleaned.append(line.rstrip())
        normalized = "\n".join(cleaned)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _repair_table_continuations(self, pages: list[object]) -> list[object]:
        previous_header: str | None = None
        previous_column_count = 0
        previous_ended_with_table = False

        for page_index, item in enumerate(pages):
            text = str(item.get("text", "")) if isinstance(item, dict) else str(item)
            table_matches = list(ATOMIC_BLOCK.finditer(text))
            first_table = next(
                (match for match in table_matches if match.lastgroup == "table"),
                None,
            )

            if (
                previous_ended_with_table
                and previous_header
                and first_table
                and not text[:first_table.start()].strip()
            ):
                lines = [
                    line.strip()
                    for line in first_table.group(0).splitlines()
                    if line.strip()
                ]
                if (
                    len(lines) >= 2
                    and TABLE_SEPARATOR.fullmatch(lines[1])
                    and self._table_column_count(lines[0]) == previous_column_count
                ):
                    repaired_table = "\n".join(
                        [previous_header, lines[1], lines[0], *lines[2:]],
                    )
                    text = (
                        text[:first_table.start()]
                        + repaired_table
                        + text[first_table.end():]
                    )
                    if isinstance(item, dict):
                        item["text"] = text
                    else:
                        pages[page_index] = text
                    table_matches = list(ATOMIC_BLOCK.finditer(text))

            last_table = next(
                (
                    match
                    for match in reversed(table_matches)
                    if match.lastgroup == "table"
                ),
                None,
            )
            previous_ended_with_table = bool(
                last_table and not text[last_table.end():].strip(),
            )
            if previous_ended_with_table and last_table:
                lines = [
                    line.strip()
                    for line in last_table.group(0).splitlines()
                    if line.strip()
                ]
                if len(lines) >= 2 and TABLE_SEPARATOR.fullmatch(lines[1]):
                    previous_header = lines[0]
                    previous_column_count = self._table_column_count(lines[0])
                else:
                    previous_header = None
                    previous_column_count = 0
            else:
                previous_header = None
                previous_column_count = 0

        return pages

    def _table_column_count(self, row: str) -> int:
        return max(row.count("|") - 1, 0)

    def _build_parent_documents(
        self,
        pages: list[LangChainDocument],
    ) -> list[LangChainDocument]:
        parents: list[LangChainDocument] = []
        for page in pages:
            sections = self._header_splitter.split_text(page.page_content)
            if not sections:
                sections = [LangChainDocument(page_content=page.page_content)]
            for section in sections:
                metadata = {**page.metadata, **section.metadata}
                for block, block_type in self._partition_atomic_blocks(section.page_content):
                    context = self._section_context(metadata)
                    if block_type == "table":
                        pieces = self._split_table(
                            block,
                            PARENT_LIMIT,
                            context,
                        )
                    elif block_type in {"image", "code"}:
                        pieces = [block]
                    else:
                        pieces = self._parent_splitter.split_text(block)
                    for piece in pieces:
                        if piece.strip():
                            parents.append(
                                LangChainDocument(
                                    page_content=piece.strip(),
                                    metadata={
                                        **metadata,
                                        "parent_id": generate_id(),
                                        "block_type": block_type,
                                    },
                                )
                            )
        return parents

    def _build_child_documents(
        self,
        parents: list[LangChainDocument],
    ) -> list[LangChainDocument]:
        children: list[LangChainDocument] = []
        for parent in parents:
            block_type = parent.metadata.get("block_type")
            if block_type == "table":
                splits = self._split_table(
                    parent.page_content,
                    CHILD_LIMIT,
                    "",
                    minimum=CHILD_MIN,
                )
            elif block_type in {"image", "code"}:
                splits = [parent.page_content]
            else:
                splits = self._child_splitter.split_text(parent.page_content)
            for split in self._merge_small_children(splits):
                children.append(
                    LangChainDocument(page_content=split, metadata=dict(parent.metadata))
                )
        return children

    def _merge_small_children(self, chunks: list[str]) -> list[str]:
        if len(chunks) < 2:
            return chunks
        merged: list[str] = []
        for chunk in chunks:
            if (
                merged
                and self._child_splitter._length_function(chunk) < CHILD_MIN
                and self._child_splitter._length_function(f"{merged[-1]}\n\n{chunk}") <= CHILD_LIMIT
            ):
                merged[-1] = f"{merged[-1]}\n\n{chunk}"
            else:
                merged.append(chunk)
        return merged

    def _partition_atomic_blocks(self, text: str) -> list[tuple[str, str]]:
        blocks: list[tuple[str, str]] = []
        cursor = 0
        for match in ATOMIC_BLOCK.finditer(text):
            if match.start() > cursor:
                blocks.append((text[cursor:match.start()], "text"))
            block_type = match.lastgroup or "text"
            blocks.append((match.group(0), block_type))
            cursor = match.end()
        if cursor < len(text):
            blocks.append((text[cursor:], "text"))
        return [(content, block_type) for content, block_type in blocks if content.strip()]

    def _section_context(self, metadata: dict) -> str:
        headings = [
            str(metadata[key]).strip()
            for _, key in HEADERS
            if metadata.get(key)
        ]
        if not headings:
            return ""
        return f"Contexto: {' > '.join(headings)}"

    def _split_table(
        self,
        table: str,
        limit: int,
        context: str,
        minimum: int = 0,
    ) -> list[str]:
        lines = [line.strip() for line in table.splitlines() if line.strip()]
        if len(lines) < 2:
            return [table.strip()]

        table_start = next(
            (index for index, line in enumerate(lines) if line.startswith("|")),
            0,
        )
        inherited_context = "\n".join(lines[:table_start]).strip()
        table_lines = lines[table_start:]
        if len(table_lines) < 2:
            return [table.strip()]
        header_size = (
            2
            if len(table_lines) > 1 and TABLE_SEPARATOR.fullmatch(table_lines[1])
            else 1
        )
        header = table_lines[:header_size]
        rows = table_lines[header_size:]
        effective_context = context or inherited_context
        prefix = "\n".join(header)
        if effective_context:
            prefix = f"{effective_context}\n\n{prefix}"
        if not rows:
            return [prefix]
        prefix_token_count = self._parent_splitter._length_function(prefix)
        header_exceeds_limit = prefix_token_count >= limit
        if header_exceeds_limit:
            logger.warning(
                "Cabecalho de tabela possui %s tokens e excede o limite de %s; "
                "o cabecalho sera preservado integralmente.",
                prefix_token_count,
                limit,
            )

        groups: list[list[str]] = []
        current: list[str] = []
        for row in rows:
            candidate = "\n".join([prefix, *current, row])
            if current and self._parent_splitter._length_function(candidate) > limit:
                groups.append(current)
                current = [row]
            else:
                current.append(row)
        if current:
            groups.append(current)

        if minimum and len(groups) > 1:
            self._rebalance_table_tail(groups, prefix, minimum, limit)
        chunks: list[str] = []
        for group in groups:
            content = "\n".join([prefix, *group]).strip()
            if (
                len(group) == 1
                and self._parent_splitter._length_function(content) > limit
                and not header_exceeds_limit
            ):
                chunks.extend(
                    self._split_oversized_table_row(prefix, group[0], limit),
                )
            else:
                chunks.append(content)
        return chunks

    def _rebalance_table_tail(
        self,
        groups: list[list[str]],
        prefix: str,
        minimum: int,
        limit: int,
    ) -> None:
        last = groups[-1]
        previous = groups[-2]
        while (
            len(previous) > 1
            and self._parent_splitter._length_function(
                "\n".join([prefix, *last]),
            )
            < minimum
        ):
            moved = previous[-1]
            candidate = "\n".join([prefix, moved, *last])
            if self._parent_splitter._length_function(candidate) > limit:
                break
            previous.pop()
            last.insert(0, moved)

    def _split_oversized_table_row(
        self,
        prefix: str,
        row: str,
        limit: int,
    ) -> list[str]:
        separator = "\n"
        prefix_tokens = self._encoding.encode(f"{prefix}{separator}")
        available = limit - len(prefix_tokens)
        if available <= 0:
            logger.warning(
                "Cabecalho de tabela excede sozinho o limite de %s tokens.",
                limit,
            )
            return [f"{prefix}{separator}{row}"]
        row_tokens = self._encoding.encode(row)
        return [
            f"{prefix}{separator}{self._encoding.decode(row_tokens[start:start + available])}".strip()
            for start in range(0, len(row_tokens), available)
        ]
