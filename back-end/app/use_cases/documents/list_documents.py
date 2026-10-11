from app.models import Document
from app.repositories import DocumentRepository


class ListDocumentsUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def execute(self, public: bool = False) -> list[Document]:
        return await self._repository.list_all(only_indexed=True) if public else await self._repository.list_all()
