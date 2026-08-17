from pathlib import Path
from unittest.mock import Mock

from app.rag.ingestion.document_ingestor import CHILD_LIMIT, PARENT_LIMIT, DocumentIngestor
from app.services import DocumentStorage


ingestor = DocumentIngestor(
    api_key="test",
    embedding_model="text-embedding-3-small",
    document_storage=DocumentStorage(Path("downloads")),
    rag_repository=Mock(),
)
pages = [
    {
        "text": (
            "# Secao A\n\n"
            + ("Texto longo para validar o splitter. " * 2000)
            + "\n\n## Secao B\n\n"
            + "| A | B |\n|---|---|\n| 1 | 2 |"
        ),
        "metadata": {"page": 0},
    }
]
parents, children = ingestor._prepare_chunks(pages)
parent_sizes = [ingestor._parent_splitter._length_function(doc.page_content) for doc in parents]
child_sizes = [
    ingestor._child_splitter._length_function(doc.page_content)
    for doc in children
]

assert parents
assert children
assert max(parent_sizes) <= PARENT_LIMIT
assert max(child_sizes) <= CHILD_LIMIT
assert any(doc.metadata.get("block_type") == "table" for doc in parents)
print(
    f"parents={len(parents)} children={len(children)} "
    f"max_parent={max(parent_sizes)} max_child={max(child_sizes)}"
)
