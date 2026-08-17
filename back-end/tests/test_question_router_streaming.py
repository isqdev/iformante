import unittest
from unittest.mock import patch

from app.rag.generation import QuestionRouter
from app.rag.models import ModelMessage


class FakeRouterModel:
    async def ainvoke(self, messages):
        return type(
            "Response",
            (),
            {"content": "Olá!", "tool_calls": []},
        )()


class QuestionRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_simple_small_talk_returns_the_router_response(self) -> None:
        router = QuestionRouter(api_key="test-key", model="test-model")

        with patch.object(
            router,
            "_get_chat_model",
            return_value=FakeRouterModel(),
        ):
            result = await router.execute(
                [ModelMessage(role="user", content="Olá!")],
            )

        self.assertEqual(result.direct_response, "Olá!")
        self.assertIsNone(result.query)


if __name__ == "__main__":
    unittest.main()
