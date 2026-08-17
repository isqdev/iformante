import asyncio
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pymupdf4llm

from app.rag.ingestion.document_ingestor import DocumentIngestor
from app.services import DocumentStorage

REFERENCE_URLS = [
    "https://ifpr.edu.br/paranavai/wp-content/uploads/sites/21/2025/01/"
    "PPC-de-Engenharia-de-Software-%E2%80%93-2025.pdf",
    "https://ifpr.edu.br/paranavai/wp-content/uploads/sites/21/2025/12/"
    "Calendario-academico-e-administrativo-2026-aprovado-pela-PROENS.pdf",
    "https://ifpr.edu.br/paranavai/wp-content/uploads/sites/21/2026/02/"
    "Tutoriais-2026-Estagio-Obrigatorio.pdf",
]


async def validate(
    selected_indexes: set[int],
    local_ppc: Path | None = None,
) -> None:
    with TemporaryDirectory() as temporary:
        storage = DocumentStorage(Path(temporary))
        ingestor = DocumentIngestor(
            api_key="validation-only",
            embedding_model="text-embedding-3-small",
            document_storage=storage,
            rag_repository=SimpleNamespace(),
        )
        results: list[dict] = []
        for index, url in enumerate(REFERENCE_URLS, start=1):
            if index not in selected_indexes:
                continue
            print(f"Validando referência {index}...", flush=True)
            if index == 1 and local_ppc is not None:
                downloaded = SimpleNamespace(filename=local_ppc.name)
                pages = [
                    {
                        "text": local_ppc.read_text(encoding="utf-8"),
                        "metadata": {"page": 0},
                    },
                ]
            else:
                downloaded = await storage.download_pdf(url, f"reference{index}")
                pages = await asyncio.to_thread(
                    pymupdf4llm.to_markdown,
                    str(downloaded.path),
                    page_chunks=True,
                    header=False,
                    footer=False,
                    show_progress=True,
                )
            cleaned_pages = ingestor._clean_pages(pages)
            parents, children = await asyncio.to_thread(
                ingestor._prepare_chunks,
                cleaned_pages,
            )
            parent_tokens = [
                ingestor._parent_splitter._length_function(parent.page_content)
                for parent in parents
            ]
            child_tokens = [
                ingestor._child_splitter._length_function(child.page_content)
                for child in children
            ]
            noise = [
                child.page_content
                for child in children
                if child.page_content.strip().isdigit()
                or "intentionally omitted" in child.page_content.lower()
                or "image omitted" in child.page_content.lower()
            ]
            table_parents = [
                parent
                for parent in parents
                if parent.metadata.get("block_type") == "table"
            ]
            table_children = [
                child
                for child in children
                if child.metadata.get("block_type") == "table"
            ]
            results.append(
                {
                    "filename": downloaded.filename,
                    "pages": len(cleaned_pages),
                    "parents": len(parents),
                    "children": len(children),
                    "table_parents": len(table_parents),
                    "table_children": len(table_children),
                    "max_parent_tokens": max(parent_tokens, default=0),
                    "max_child_tokens": max(child_tokens, default=0),
                    "children_under_32_tokens": sum(
                        count < 32 for count in child_tokens
                    ),
                    "noise_chunks": len(noise),
                    "noise_previews": [item[:200] for item in noise[:3]],
                    "largest_child_preview": (
                        max(
                            children,
                            key=lambda child: ingestor._child_splitter._length_function(
                                child.page_content,
                            ),
                        ).page_content[:500]
                        if children
                        else ""
                    ),
                },
            )
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--index",
        type=int,
        action="append",
        choices=range(1, len(REFERENCE_URLS) + 1),
    )
    parser.add_argument("--local-ppc", type=Path)
    arguments = parser.parse_args()
    asyncio.run(
        validate(
            set(arguments.index or range(1, len(REFERENCE_URLS) + 1)),
            arguments.local_ppc,
        ),
    )
