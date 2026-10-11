from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Message, MessageSource


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, message: Message) -> Message:
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_by_id(self, message_id: str) -> Message | None:
        return await self._session.get(Message, message_id)

    async def list_by_conversation(self, conversation_id: str) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .options(
                selectinload(Message.sources).selectinload(
                    MessageSource.document,
                ),
            )
            .order_by(Message.created_at.asc()),
        )
        return list(result.scalars().all())

    async def list_model_history(
        self,
        conversation_id: str,
    ) -> list[Any]:
        result = await self._session.execute(
            select(Message.author, Message.content, Message.playback_status)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc()),
        )
        return list(result.all())

    async def list_recent_by_conversation(
        self,
        conversation_id: str,
        limit: int,
    ) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit),
        )
        messages = list(result.scalars().all())
        messages.reverse()
        return messages
