import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.use_cases.conversations import (
    GetConversationUseCase,
    ListConversationsUseCase,
)


class ConversationUseCaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_lists_conversations_for_anonymous_owner(self) -> None:
        conversations = [SimpleNamespace(id="conversation-1")]
        repository = SimpleNamespace(
            list_by_anonymous_id=AsyncMock(return_value=conversations),
        )
        use_case = ListConversationsUseCase(repository)

        result = await use_case.execute("anonymous-1")

        self.assertEqual(result, conversations)
        repository.list_by_anonymous_id.assert_awaited_once_with("anonymous-1")

    async def test_returns_conversation_with_messages_for_owner(self) -> None:
        conversation = SimpleNamespace(
            id="conversation-1",
            anonymous_id="anonymous-1",
        )
        messages = [SimpleNamespace(id="message-1")]
        conversation_repository = SimpleNamespace(
            get_by_id=AsyncMock(return_value=conversation),
        )
        message_repository = SimpleNamespace(
            list_by_conversation=AsyncMock(return_value=messages),
        )
        use_case = GetConversationUseCase(
            conversation_repository=conversation_repository,
            message_repository=message_repository,
        )

        result = await use_case.execute("conversation-1", "anonymous-1")

        self.assertIsNotNone(result)
        self.assertEqual(result.conversation, conversation)
        self.assertEqual(result.messages, messages)

    async def test_hides_conversation_from_another_owner(self) -> None:
        conversation = SimpleNamespace(
            id="conversation-1",
            anonymous_id="anonymous-2",
        )
        conversation_repository = SimpleNamespace(
            get_by_id=AsyncMock(return_value=conversation),
        )
        message_repository = SimpleNamespace(
            list_by_conversation=AsyncMock(),
        )
        use_case = GetConversationUseCase(
            conversation_repository=conversation_repository,
            message_repository=message_repository,
        )

        result = await use_case.execute("conversation-1", "anonymous-1")

        self.assertIsNone(result)
        message_repository.list_by_conversation.assert_not_awaited()
