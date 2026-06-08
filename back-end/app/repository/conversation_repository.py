from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation: Conversation) -> Conversation:
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get_by_id(self, conversation_id: str) -> Conversation | None:
        return await self._session.get(Conversation, conversation_id)

    async def list_by_user(self, user_id: str) -> list[Conversation]:
        result = await self._session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc()),
        )
        return list(result.scalars().all())

    async def list_by_anonymous_id(self, anonymous_id: str) -> list[Conversation]:
        result = await self._session.execute(
            select(Conversation)
            .where(Conversation.anonymous_id == anonymous_id)
            .order_by(Conversation.updated_at.desc()),
        )
        return list(result.scalars().all())
