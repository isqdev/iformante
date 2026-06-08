from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document: Document) -> Document:
        self._session.add(document)
        await self._session.flush()
        return document

    async def get_by_id(self, document_id: str) -> Document | None:
        return await self._session.get(Document, document_id)

    async def list_by_uploader(self, user_id: str) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .where(Document.uploaded_by == user_id)
            .order_by(Document.created_at.desc()),
        )
        return list(result.scalars().all())
