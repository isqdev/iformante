from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MessageSource


class MessageSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, sources: list[MessageSource]) -> None:
        self._session.add_all(sources)
        await self._session.flush()

    async def list_by_message(self, message_id: str) -> list[MessageSource]:
        result = await self._session.execute(
            select(MessageSource)
            .where(MessageSource.message_id == message_id)
            .options(selectinload(MessageSource.document))
            .order_by(MessageSource.rank)
        )
        return list(result.scalars().all())
