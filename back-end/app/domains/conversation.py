from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, MessageAuthor
from app.repository import ConversationRepository, MessageRepository


class ConversationDomain:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._conversation_repository = ConversationRepository(session)
        self._message_repository = MessageRepository(session)

    async def list_conversations(self, anonymous_id: str) -> list[Conversation]:
        return await self._conversation_repository.list_by_anonymous_id(anonymous_id)

    async def get_conversation(
        self,
        conversation_id: str,
        anonymous_id: str,
    ) -> Conversation | None:
        conversation = await self._conversation_repository.get_by_id(conversation_id)

        if not conversation or conversation.anonymous_id != anonymous_id:
            return None

        return conversation

    async def list_messages(self, conversation_id: str) -> list[Message]:
        return await self._message_repository.list_by_conversation(conversation_id)

    async def create_or_get_conversation(
        self,
        conversation_id: str | None,
        anonymous_id: str,
        first_message: str,
    ) -> Conversation:
        if conversation_id:
            conversation = await self.get_conversation(conversation_id, anonymous_id)

            if not conversation:
                raise ValueError("Conversa nao encontrada.")

            return conversation

        conversation = Conversation(
            anonymous_id=anonymous_id,
            title=self._build_title(first_message),
        )
        await self._conversation_repository.create(conversation)
        return conversation

    async def create_user_message(
        self,
        conversation_id: str,
        content: str,
    ) -> Message:
        return await self._message_repository.create(
            Message(
                conversation_id=conversation_id,
                author=MessageAuthor.USER.value,
                content=content,
            ),
        )

    async def create_assistant_message(
        self,
        conversation_id: str,
        content: str,
    ) -> Message:
        return await self._message_repository.create(
            Message(
                conversation_id=conversation_id,
                author=MessageAuthor.AI.value,
                content=content,
            ),
        )

    async def touch_conversation(self, conversation: Conversation) -> None:
        conversation.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    def _build_title(self, content: str) -> str:
        title = " ".join(content.split())

        if len(title) <= 48:
            return title

        return f"{title[:48].rstrip()}..."
