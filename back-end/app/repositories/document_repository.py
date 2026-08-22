from sqlalchemy import select
from sqlalchemy.orm import selectinload
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
        result = await self._session.execute(
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.uploaded_by_user)),
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .options(selectinload(Document.uploaded_by_user))
            .order_by(Document.created_at.desc()),
        )
        return list(result.scalars().all())

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)
        await self._session.flush()

    async def rename(self, document: Document, title: str) -> Document:
        document.title = title
        await self._session.flush()
        return document

    async def list_by_uploader(self, user_id: str) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .where(Document.uploaded_by == user_id)
            .order_by(Document.created_at.desc()),
        )
        return list(result.scalars().all())
