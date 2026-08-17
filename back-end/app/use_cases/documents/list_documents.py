from app.models import Document
from app.repositories import DocumentRepository


class ListDocumentsUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def execute(self) -> list[Document]:
        return await self._repository.list_all()
