from dataclasses import dataclass
from pathlib import Path
import shutil

from app.repositories import DocumentRepository, UnitOfWork


@dataclass(frozen=True)
class DeleteDocumentResult:
    document_id: str


class DeleteDocumentUseCase:
    def __init__(self, document_repository: DocumentRepository, unit_of_work: UnitOfWork, storage_dir: Path) -> None:
        self._document_repository = document_repository
        self._unit_of_work = unit_of_work
        self._storage_dir = storage_dir

    async def execute(self, document_id: str) -> DeleteDocumentResult:
        document = await self._document_repository.get_by_id(document_id.strip())
        if document is None:
            raise ValueError("Documento nao encontrado.")
        await self._document_repository.delete(document)
        await self._unit_of_work.commit()
        target = (self._storage_dir / document.id).resolve()
        storage_root = self._storage_dir.resolve()
        if target.parent == storage_root:
            shutil.rmtree(target, ignore_errors=True)
        return DeleteDocumentResult(document.id)
