from dataclasses import dataclass

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
        anonymous_id: str,
    ) -> GetConversationResult | None:
        conversation = await self._conversation_repository.get_by_id(conversation_id)

        if not conversation or conversation.anonymous_id != anonymous_id:
            return None

        messages = await self._message_repository.list_by_conversation(conversation.id)
        return GetConversationResult(conversation=conversation, messages=messages)
