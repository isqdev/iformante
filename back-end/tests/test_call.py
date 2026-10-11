import asyncio
import base64
import json
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.factories.chat import get_receive_message_use_case
from app.rag.generation import AnswerGenerator
from app.rag.retrieval import RetrievedParent
from app.routes import call
from app.security.dependencies import optional_current_user
from app.services.call_audio import GroqTranscriber, PiperService, audio_extension
from app.services.speech_text import ResponseMode, SPEECH_FALLBACK, normalize_speech, within_speech_budget
from app.use_cases.chat.receive_message import ChatStreamEvent


class SpeechTextTests(unittest.TestCase):
    def test_numbers_dates_percentages_count_as_spoken_words(self):
        text = normalize_speech("**Prazo:** 21/10/2026, às 08:30. São 1.200 horas e 10% no IFPR.")
        self.assertIn("vinte e um de outubro", text)
        self.assertIn("oito horas e trinta minutos", text)
        self.assertIn("mil e duzentos", text)
        self.assertIn("dez por cento", text)
        self.assertIn("Instituto Federal do Paraná", text)
        self.assertNotIn("2026", text)

    def test_removes_metadata_and_markup_from_reading(self):
        self.assertEqual(normalize_speech('# Olá!\n[Resposta](https://example.com)\n```json\n{"used_sources": ["parent_1"]}\n```'), "Olá! Resposta")

    def test_money_is_read_with_currency_and_cents(self):
        self.assertEqual(normalize_speech("R$ 1.200,50"), "mil e duzentos reais e cinquenta centavos")
        self.assertEqual(normalize_speech("R$1,00"), "um real")

    def test_budget_rejects_overflow_and_empty(self):
        self.assertTrue(within_speech_budget(" ".join(["palavra"] * 40)))
        self.assertFalse(within_speech_budget(" ".join(["palavra"] * 41)))
        self.assertFalse(within_speech_budget(" "))

    def test_file_signature_not_filename_decides_format(self):
        self.assertEqual(audio_extension(b"\x1a\x45\xdf\xa3audio"), "webm")
        self.assertEqual(audio_extension(b"RIFF1234WAVEaudio"), "wav")
        with self.assertRaises(ValueError):
            audio_extension(b"not really a webm file")


class SpeechGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_overlong_answer_is_retried_then_safe_fallback(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content=" ".join(["palavra"] * 41))))
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.speech_answer("Pergunta", [])
        self.assertEqual(model.ainvoke.await_count, 2)
        self.assertEqual(result.content, SPEECH_FALLBACK)
        self.assertEqual(result.used_parent_ids, [])

    async def test_spoken_response_preserves_source_metadata(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content='O prazo é 21/10/2026.\n```json\n{"used_sources": ["parent_1"]}\n```')))
        parent = RetrievedParent(id="parent001", document_id="doc000001", content="Prazo de inscrição", bbox=None, source_url=None, filename="edital.pdf")
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.speech_answer("Prazo?", [parent])
        self.assertEqual(result.used_parent_ids, ["parent001"])
        self.assertTrue(within_speech_budget(result.content))
        self.assertNotIn("used_sources", result.content)

    async def test_direct_router_response_also_has_hard_budget(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content=" ".join(["longo"] * 90))))
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            self.assertEqual(await generator.prepare_direct_speech(" ".join(["longo"] * 60)), SPEECH_FALLBACK)
        model.ainvoke.assert_awaited_once()

    async def test_piper_independently_rejects_unvalidated_text(self):
        service = PiperService("nonexistent.onnx")
        with self.assertRaises(ValueError):
            async for _ in service.stream(" ".join(["longo"] * 41)):
                pass

    async def test_empty_transcription_never_becomes_a_router_message(self):
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"text": "", "segments": []})
        client = AsyncMock()
        client.post.return_value = response
        client.__aenter__.return_value = client
        with patch("app.services.call_audio.httpx.AsyncClient", return_value=client):
            with self.assertRaisesRegex(ValueError, "Nenhuma fala"):
                await GroqTranscriber("test-key").transcribe(b"\x1a\x45\xdf\xa3audio")
        kwargs = client.post.call_args.kwargs
        self.assertEqual(kwargs["data"]["model"], "whisper-large-v3-turbo")
        self.assertEqual(kwargs["data"]["language"], "pt")


class FakeCallUseCase:
    is_configured = True
    modes = []
    requests = []

    async def stream(self, **kwargs):
        self.modes.append(kwargs["response_mode"])
        self.requests.append(kwargs)
        yield ChatStreamEvent("delta", {"content": "Olá!"})
        yield ChatStreamEvent("done", {"message_id": "msgai0001", "sources": []})


class FakePiper:
    configured = True
    async def stream(self, text):
        yield "audio_format", {"sample_rate": 22050, "channels": 1, "sample_width": 2}
        yield "audio", {"sequence": 0, "data": base64.b64encode(b"\0\0" * 100).decode()}
        yield "audio_done", {"samples": 100}


class CallRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(call.router)
        self.app.dependency_overrides[optional_current_user] = lambda: None
        self.app.dependency_overrides[get_receive_message_use_case] = FakeCallUseCase
        self.client = TestClient(self.app)
        FakeCallUseCase.modes.clear()
        FakeCallUseCase.requests.clear()

    def tearDown(self):
        call.active_turns.clear()

    def test_route_forces_speech_and_streams_audio_after_approved_answer(self):
        with patch.object(call, "settings", replace(call.settings, groq_api_key="test-key")), patch.object(call, "piper_service", FakePiper()), patch.object(GroqTranscriber, "transcribe", AsyncMock(return_value="Olá")):
            response = self.client.post("/call/stream", files={"audio": ("recording.webm", b"\x1a\x45\xdf\xa3audio", "audio/webm")}, data={"turn_id": "12345678-1234-1234-1234-123456789012", "response_mode": "text"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeCallUseCase.modes, [ResponseMode.SPEECH])
        self.assertLess(response.text.index("event: answer"), response.text.index("event: audio\n"))
        self.assertIn("event: transcript", response.text)
        self.assertIn("event: done", response.text)
        self.assertFalse(call.active_turns)

    def test_invalid_file_does_not_reach_transcriber(self):
        with patch.object(call, "settings", replace(call.settings, groq_api_key="test-key")), patch.object(call, "piper_service", FakePiper()), patch.object(GroqTranscriber, "transcribe", AsyncMock()) as transcribe:
            response = self.client.post("/call/stream", files={"audio": ("fake.webm", b"plain text", "audio/webm")}, data={"turn_id": "12345678-1234-1234-1234-123456789012"})
        self.assertEqual(response.status_code, 400)
        transcribe.assert_not_called()

    def test_signed_in_call_uses_temporary_context_even_with_conversation_id(self):
        self.app.dependency_overrides[optional_current_user] = lambda: SimpleNamespace(id="signed001")
        with patch.object(call, "settings", replace(call.settings, groq_api_key="test-key")), patch.object(call, "piper_service", FakePiper()), patch.object(GroqTranscriber, "transcribe", AsyncMock(return_value="Outra pergunta")):
            response = self.client.post("/call/stream", files={"audio": ("recording.webm", b"\x1a\x45\xdf\xa3audio", "audio/webm")}, data={"turn_id": "12345678-1234-1234-1234-123456789012", "conversation_id": "oldconv01", "messages": json.dumps([{"role": "user", "content": "Primeira pergunta"}])})
        self.assertEqual(response.status_code, 200)
        received = FakeCallUseCase.requests[0]
        self.assertIsNone(received["conversation_id"])
        self.assertIsNone(received["user_id"])
        self.assertIsNone(received["anonymous_id"])
        self.assertEqual(received["history"][0].content, "Primeira pergunta")
        self.assertNotIn("event: conversation", response.text)

    def test_legacy_playback_endpoint_never_persists_calls(self):
        self.app.dependency_overrides[optional_current_user] = lambda: SimpleNamespace(id="signed001")
        response = self.client.post("/call/playback", json={"message_id": "msgai0001", "status": "completed"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"saved": False})

    def test_cancel_does_not_cancel_another_users_turn(self):
        token = "12345678-1234-1234-1234-123456789012"
        turn = call.ActiveTurn("someone-else")
        call.active_turns[token] = turn
        self.client.post("/call/cancel", json={"turn_id": token})
        self.assertFalse(turn.cancelled)


if __name__ == "__main__":
    unittest.main()
