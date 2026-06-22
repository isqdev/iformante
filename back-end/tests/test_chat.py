import asyncio
import string
import unittest
from collections.abc import AsyncIterator
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from app.app import app
from app.routes.chat import (
    ANONYMOUS_COOKIE_NAME,
    get_receive_message_use_case,
)
from app.use_cases import (
    ChatStreamEvent,
    ReplyMessageUseCase,
    RouteOrRetrieveMessageUseCase,
)
from app.schemas import ChatMessage


class FakeReceiveMessageUseCase:
    is_configured = True

    async def stream(self, conversation_id, anonymous_id, message) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(
            "conversation",
            {
                "conversation_id": "chat12345",
                "title": "Hello",
                "message_id": "msguser01",
            },
        )
        yield ChatStreamEvent("delta", {"content": "Hello"})
        yield ChatStreamEvent("delta", {"content": " world"})
        yield ChatStreamEvent("done", {"message_id": "msgai0001"})


class ChatTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_receive_message_use_case] = FakeReceiveMessageUseCase
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
        self.assertEqual(len(cookie or ""), 5)
        self.assertTrue(
            all(character in string.ascii_letters + string.digits for character in cookie or ""),
        )

    def test_chat_stream_rejects_empty_messages(self) -> None:
        response = self.client.post(
            "/chat/stream",
            json={"messages": [{"role": "user", "content": "   "}]},
        )

        self.assertEqual(response.status_code, 400)


class RouteOrRetrieveMessageUseCaseTests(unittest.TestCase):
    def test_returns_direct_response_without_tool_call(self) -> None:
        class FakeModel:
            async def ainvoke(self, messages):
                class Response:
                    content = "Ola! Como posso ajudar sobre o IF?"
                    tool_calls = []

                return Response()

        use_case = RouteOrRetrieveMessageUseCase(
            api_key="test-key",
            model="test-model",
            top_k=4,
        )

        async def run_test():
            with patch.object(use_case, "_get_chat_model", return_value=FakeModel()):
                return await use_case.execute([ChatMessage(role="user", content="oi")])

        result = asyncio.run(run_test())

        self.assertEqual(result.direct_response, "Ola! Como posso ajudar sobre o IF?")
        self.assertIsNone(result.query)
        self.assertEqual(result.documents, [])

    def test_tool_call_builds_query_and_retrieves_context(self) -> None:
        class FakeModel:
            async def ainvoke(self, messages):
                class Response:
                    content = ""
                    tool_calls = [
                        {
                            "name": "buscar_documentos",
                            "args": {
                                "query": "prazos edital",
                                "user_question": "Quais sao os prazos do edital?",
                            },
                        },
                    ]

                return Response()

        expected_documents = [
            Document(page_content="Prazos", metadata={"title": "Edital"}),
        ]
        use_case = RouteOrRetrieveMessageUseCase(
            api_key="test-key",
            model="test-model",
            top_k=4,
        )

        async def run_test():
            with patch.object(
                use_case,
                "_get_chat_model",
                return_value=FakeModel(),
            ), patch.object(
                use_case,
                "_retrieve_context",
                return_value=expected_documents,
            ) as retrieve_context:
                result = await use_case.execute(
                    [ChatMessage(role="user", content="Quais sao os prazos?")],
                )
                return result, retrieve_context

        result, retrieve_context = asyncio.run(run_test())

        self.assertEqual(result.query, "prazos edital")
        self.assertEqual(result.user_question, "Quais sao os prazos do edital?")
        self.assertEqual(result.documents, expected_documents)
        retrieve_context.assert_called_once_with("prazos edital")

    def test_tool_call_requires_query_and_user_question(self) -> None:
        class FakeModel:
            async def ainvoke(self, messages):
                class Response:
                    content = ""
                    tool_calls = [
                        {
                            "name": "buscar_documentos",
                            "args": {
                                "query": "prazos edital",
                            },
                        },
                    ]

                return Response()

        use_case = RouteOrRetrieveMessageUseCase(
            api_key="test-key",
            model="test-model",
            top_k=4,
        )

        async def run_test():
            with patch.object(use_case, "_get_chat_model", return_value=FakeModel()):
                return await use_case.execute(
                    [ChatMessage(role="user", content="Quais sao os prazos?")],
                )

        with self.assertRaisesRegex(ValueError, "query e user_question"):
            asyncio.run(run_test())


class ReplyMessageUseCaseTests(unittest.TestCase):
    def test_streams_answer_from_retrieved_context(self) -> None:
        class FakeAnswerModel:
            async def astream(self, messages):
                self.messages = messages

                class Chunk:
                    content = "Resposta"

                yield Chunk()

        use_case = ReplyMessageUseCase(api_key="test-key", model="test-model")

        async def run_test() -> list[str]:
            with patch.object(use_case, "_get_chat_model", return_value=FakeAnswerModel()):
                return [
                    chunk
                    async for chunk in use_case.stream(
                        "Pergunta",
                        [
                            Document(
                                page_content="Secao\n\nconteudo original",
                                metadata={
                                    "title": "Documento",
                                    "type": "paragraph",
                                    "page": 1,
                                    "section_path": ["Secao"],
                                },
                            ),
                        ],
                    )
                ]

        self.assertEqual(asyncio.run(run_test()), ["Resposta"])

    def test_returns_not_found_when_context_is_empty(self) -> None:
        use_case = ReplyMessageUseCase(api_key="test-key", model="test-model")

        async def run_test() -> list[str]:
            return [
                chunk
                async for chunk in use_case.stream(
                    "Pergunta",
                    [],
                )
            ]

        self.assertEqual(
            asyncio.run(run_test()),
            ["Nao encontrei essa informacao nos documentos disponiveis."],
        )


if __name__ == "__main__":
    unittest.main()
