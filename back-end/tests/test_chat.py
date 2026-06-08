import unittest
import string
from collections.abc import AsyncIterator
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.domains.chat import ChatDomain
from app.app import app
from app.routes.chat import ANONYMOUS_COOKIE_NAME, get_chat_domain, get_conversation_domain
from model.chat import ChatMessage


class FakeChatDomain:
    is_configured = True

    async def stream_response(self, messages) -> AsyncIterator[str]:
        for chunk in ["Hello", " world"]:
            yield chunk


class FakeConversation:
    id = "chat12345"
    title = "Hello"


class FakeUserMessage:
    id = "msguser01"


class FakeAssistantMessage:
    id = "msgai0001"


class FakeConversationDomain:
    async def create_or_get_conversation(self, conversation_id, anonymous_id, first_message):
        self.anonymous_id = anonymous_id
        return FakeConversation()

    async def list_messages(self, conversation_id):
        return []

    async def create_user_message(self, conversation_id, content):
        return FakeUserMessage()

    async def create_assistant_message(self, conversation_id, content):
        self.assistant_content = content
        return FakeAssistantMessage()

    async def touch_conversation(self, conversation):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


class ChatTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_chat_domain] = FakeChatDomain
        app.dependency_overrides[get_conversation_domain] = FakeConversationDomain
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_chat_stream_returns_response(self) -> None:
        response = self.client.post(
            "/chat/stream",
            json={"message": "Hello"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: conversation", response.text)
        self.assertIn("event: delta", response.text)
        self.assertIn("Hello", response.text)
        self.assertIn("world", response.text)
        self.assertIn("event: done", response.text)
        self.assertIn(ANONYMOUS_COOKIE_NAME, response.headers["set-cookie"])

    def test_anonymous_cookie_uses_project_id_format(self) -> None:
        response = self.client.post(
            "/chat/stream",
            json={"message": "Hello"},
        )
        cookie = response.cookies.get(ANONYMOUS_COOKIE_NAME)

        self.assertIsNotNone(cookie)
        self.assertEqual(len(cookie or ""), 9)
        self.assertTrue(
            all(character in string.ascii_letters + string.digits for character in cookie or ""),
        )

    def test_chat_stream_rejects_empty_messages(self) -> None:
        response = self.client.post(
            "/chat/stream",
            json={"messages": [{"role": "user", "content": "   "}]},
        )

        self.assertEqual(response.status_code, 400)


class ChatDomainTests(unittest.TestCase):
    def test_rejects_empty_messages(self) -> None:
        domain = ChatDomain(
            api_key="test-key",
            model="test-model",
            top_k=4,
        )

        async def run_test() -> None:
            with self.assertRaises(ValueError):
                async for _ in domain.stream_response(
                    [ChatMessage(role="user", content="   ")],
                ):
                    pass

        import asyncio

        asyncio.run(run_test())

    def test_streams_agent_text_chunks(self) -> None:
        class FakeAgent:
            async def astream(self, payload, stream_mode):
                self.payload = payload
                self.stream_mode = stream_mode

                class Chunk:
                    content = "Resposta"

                yield Chunk(), {"langgraph_node": "model"}
                yield Chunk(), {"langgraph_node": "tools"}

        domain = ChatDomain(
            api_key="test-key",
            model="test-model",
            top_k=4,
        )

        async def run_test() -> list[str]:
            with patch.object(domain, "_build_agent", return_value=FakeAgent()):
                return [
                    chunk
                    async for chunk in domain.stream_response(
                        [ChatMessage(role="user", content="Pergunta")],
                    )
                ]

        import asyncio

        self.assertEqual(asyncio.run(run_test()), ["Resposta"])

    def test_agent_name_is_openai_compatible(self) -> None:
        domain = ChatDomain(
            api_key="test-key",
            model="test-model",
            top_k=4,
        )

        self.assertEqual(domain._agent_name, "agentic_rag")
        self.assertNotIn(" ", domain._agent_name)


if __name__ == "__main__":
    unittest.main()
