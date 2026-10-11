from dataclasses import dataclass
from datetime import UTC, datetime

from app.models import Conversation, Message
from app.repositories import ConversationRepository, MessageRepository


@dataclass(frozen=True)
class GetConversationResult:
    conversation: Conversation
    messages: list[Message]


class GetConversationUseCase:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._message_repository = message_repository

    async def execute(
        self,
        conversation_id: str,
        user_id: str,
    ) -> GetConversationResult | None:
        conversation = await self._conversation_repository.get_by_id(conversation_id)

        if not conversation or conversation.user_id != user_id or conversation.expires_at <= datetime.now(UTC):
            return None

        messages = await self._message_repository.list_by_conversation(conversation.id)
        return GetConversationResult(conversation=conversation, messages=messages)
