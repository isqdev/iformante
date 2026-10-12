import asyncio
import base64
import json
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.factories.chat import get_receive_message_use_case
from app.rag.generation import AnswerGenerator
from app.rag.retrieval import RetrievedParent
from app.routes import call
from app.security.dependencies import optional_current_user
from app.services.call_audio import GroqTranscriber, PocketTTSService, _stream_pocket_tts, audio_extension
from app.services.speech_text import ResponseMode, normalize_speech
from app.use_cases.chat.receive_message import ChatStreamEvent
from scripts.install_call_voice import write_local_config


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

    def test_normalization_preserves_response_even_when_dates_expand_past_limit(self):
        text = " ".join(["palavra"] * 50) + " até 21/10/2026."
        self.assertGreater(len(normalize_speech(text).split()), 60)
        self.assertIn("vinte e um de outubro", normalize_speech(text))

    def test_paragraph_pause_and_existing_punctuation_are_preserved(self):
        self.assertEqual(normalize_speech("O curso é gratuito\n\nVocê precisa se inscrever."), "O curso é gratuito. Você precisa se inscrever.")
        self.assertEqual(normalize_speech("O curso é gratuito!\n\nVocê precisa se inscrever."), "O curso é gratuito! Você precisa se inscrever.")
        self.assertEqual(normalize_speech("Você pode fazer\numa inscrição."), "Você pode fazer uma inscrição.")

    def test_singular_time_and_first_day_sound_natural(self):
        self.assertEqual(normalize_speech("Às 01:01, em 01/10/2026."), "À uma hora e um minuto, em primeiro de outubro de dois mil e vinte e seis.")
        self.assertEqual(normalize_speech("Às 21:01 e às 22:02."), "Às vinte e uma horas e um minuto e às vinte e duas horas e dois minutos.")

    def test_negative_number_is_not_confused_with_a_list_marker(self):
        self.assertEqual(normalize_speech("-10 graus."), "menos dez graus.")

    def test_file_signature_not_filename_decides_format(self):
        self.assertEqual(audio_extension(b"\x1a\x45\xdf\xa3audio"), "webm")
        self.assertEqual(audio_extension(b"RIFF1234WAVEaudio"), "wav")
        with self.assertRaises(ValueError):
            audio_extension(b"not really a webm file")


class SpeechGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_overlong_answer_is_returned_without_retry_or_fallback(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content=" ".join(["palavra"] * 61))))
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.speech_answer("Pergunta", [])
        model.ainvoke.assert_awaited_once()
        self.assertEqual(result.content, " ".join(["palavra"] * 61))
        self.assertEqual(result.used_parent_ids, [])

    async def test_spoken_response_preserves_source_metadata(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content='O prazo é 21/10/2026.\n```json\n{"used_sources": ["parent_1"]}\n```')))
        parent = RetrievedParent(id="parent001", document_id="doc000001", content="Prazo de inscrição", bbox=None, source_url=None, filename="edital.pdf")
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.speech_answer("Prazo?", [parent])
        self.assertEqual(result.used_parent_ids, ["parent001"])
        self.assertNotIn("used_sources", result.content)

    async def test_direct_router_response_is_returned_past_limit_without_retry(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content=" ".join(["longo"] * 90))))
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            self.assertEqual(await generator.prepare_direct_speech(" ".join(["longo"] * 61)), " ".join(["longo"] * 90))
        model.ainvoke.assert_awaited_once()

    async def test_answer_between_old_and_new_limits_is_accepted_without_shortening(self):
        spoken = " ".join(["palavra"] * 55) + "."
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content=spoken)))
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.speech_answer("Pergunta", [])
        self.assertEqual(result.content, spoken)
        model.ainvoke.assert_awaited_once()

    async def test_structured_answer_is_normalized_without_retry_or_losing_source_ids(self):
        model = SimpleNamespace(ainvoke=AsyncMock(side_effect=[
            SimpleNamespace(content='Prazo: 21/10/2026.\n```json\n{"used_sources": ["parent_1"]}\n```'),
            SimpleNamespace(content='Você pode se inscrever até 21/10/2026.\n```json\n{"used_sources": ["parent_1"]}\n```'),
        ]))
        parent = RetrievedParent(id="parent001", document_id="doc000001", content="Inscrições até 21/10/2026", bbox=None, source_url=None, filename="edital.pdf")
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.speech_answer("Até quando posso me inscrever?", [parent])
        model.ainvoke.assert_awaited_once()
        self.assertEqual(result.content, "Prazo: vinte e um de outubro de dois mil e vinte e seis.")
        self.assertEqual(result.used_parent_ids, ["parent001"])

    async def test_question_echo_does_not_trigger_another_generation(self):
        model = SimpleNamespace(ainvoke=AsyncMock(side_effect=[
            SimpleNamespace(content="Você perguntou se a inscrição é gratuita. Ela é gratuita."),
            SimpleNamespace(content="A inscrição é gratuita."),
        ]))
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.speech_answer("A inscrição é gratuita?", [])
        self.assertEqual(result.content, "Você perguntou se a inscrição é gratuita. Ela é gratuita.")
        model.ainvoke.assert_awaited_once()

    async def test_short_direct_response_also_gets_oral_presentation(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content="De nada!")))
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            self.assertEqual(await generator.prepare_direct_speech("Disponha."), "De nada!")
        model.ainvoke.assert_awaited_once()

    async def test_scope_refusal_remains_exact_without_rewriting(self):
        model = SimpleNamespace(ainvoke=AsyncMock())
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            self.assertEqual(await generator.prepare_direct_speech("Não posso ajudar com isso."), "Não posso ajudar com isso.")
        model.ainvoke.assert_not_awaited()

    async def test_direct_list_is_rewritten_before_number_normalization(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content="Você precisa apresentar o documento de identificação e o histórico escolar.")))
        generator = AnswerGenerator("test-key", "test-model")
        original = "1. Documento de identificação\n2. Histórico escolar"
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.prepare_direct_speech(original)
        self.assertEqual(model.ainvoke.call_args.args[0][1].content, original)
        self.assertNotIn("um.", result)
        self.assertIn("histórico escolar", result)

    async def test_structured_output_is_returned_without_fallback(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content="Prazo: amanhã.")))
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.speech_answer("Qual é o prazo?", [])
        model.ainvoke.assert_awaited_once()
        self.assertEqual(result.content, "Prazo: amanhã.")

    async def test_pocket_tts_sends_overlong_text_to_worker(self):
        service = PocketTTSService("nonexistent.yaml", "nonexistent.safetensors")
        service._process = SimpleNamespace(is_alive=lambda: True)
        service._connection = Mock()
        service._ready = True
        service._receive = AsyncMock(return_value=("audio_done", {"samples": 0}))
        text = " ".join(["longo"] * 90)
        events = [event async for event in service.stream(text)]
        service._connection.send.assert_called_once_with(text)
        self.assertEqual(events, [("audio_done", {"samples": 0})])

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


class PocketTTSAudioTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_config_loads_with_windows_encoding_without_remote_assets(self):
        import yaml

        with TemporaryDirectory() as folder:
            target = Path(folder)
            write_local_config(target)
            path = target / "portuguese.yaml"
            self.assertTrue(path.read_bytes().isascii())
            config = yaml.safe_load(path.read_text(encoding="cp1252"))
            self.assertEqual(config["weights_path"], str(target / "model.safetensors"))
            self.assertIsNone(config["weights_path_without_voice_cloning"])
            self.assertEqual(config["flow_lm"]["lookup_table"]["tokenizer_path"], str(target / "tokenizer.json"))

    async def test_brazilian_stream_converts_float_audio_and_preserves_frame_order(self):
        import numpy as np

        sent = []
        connection = SimpleNamespace(send=sent.append)
        calls = []

        state = {"george": "cached-state"}

        def generate_audio_stream(voice_state, text, **kwargs):
            calls.append((voice_state, text, kwargs))
            for samples in (np.array([-2, -1, 0, 1, 2], dtype=np.float32), np.ones(3000, dtype=np.float32) * 0.5):
                chunk = Mock()
                chunk.detach.return_value.cpu.return_value.numpy.return_value = samples
                yield chunk

        _stream_pocket_tts(connection, SimpleNamespace(generate_audio_stream=generate_audio_stream, sample_rate=24000), state, "Olá")
        self.assertEqual(calls, [(state, "Olá", {"copy_state": True})])
        self.assertEqual(sent[0], ("audio_format", {"sample_rate": 24000, "channels": 1, "sample_width": 2}))
        frames = [payload for event, payload in sent if event == "audio"]
        self.assertEqual([frame["sequence"] for frame in frames], [0, 1, 2])
        self.assertTrue(all(len(base64.b64decode(frame["data"])) <= 4800 for frame in frames))
        raw = b"".join(base64.b64decode(frame["data"]) for frame in frames)
        self.assertEqual(np.frombuffer(raw, dtype="<i2")[:5].tolist(), [-32767, -32767, 0, 32767, 32767])
        self.assertEqual(sent[-1], ("audio_done", {"samples": 3005}))

    async def test_configuration_requires_portuguese_config_model_tokenizer_and_george(self):
        with TemporaryDirectory() as folder:
            model = Path(folder) / "model.safetensors"
            config = Path(folder) / "portuguese.yaml"
            tokenizer = Path(folder) / "tokenizer.json"
            voice = Path(folder) / "george.safetensors"
            service = PocketTTSService(str(config), str(voice))
            config.touch()
            model.touch()
            self.assertFalse(service.configured)
            tokenizer.touch()
            self.assertFalse(service.configured)
            voice.touch()
            self.assertTrue(service.configured)


class FakeCallUseCase:
    is_configured = True
    modes = []
    requests = []

    async def stream(self, **kwargs):
        self.modes.append(kwargs["response_mode"])
        self.requests.append(kwargs)
        yield ChatStreamEvent("delta", {"content": "Olá!"})
        yield ChatStreamEvent("done", {"message_id": "msgai0001", "sources": []})


class FakePocketTTS:
    configured = True
    async def stream(self, text):
        yield "audio_format", {"sample_rate": 24000, "channels": 1, "sample_width": 2}
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
        with patch.object(call, "settings", replace(call.settings, groq_api_key="test-key")), patch.object(call, "voice_service", FakePocketTTS()), patch.object(GroqTranscriber, "transcribe", AsyncMock(return_value="Olá")):
            response = self.client.post("/call/stream", files={"audio": ("recording.webm", b"\x1a\x45\xdf\xa3audio", "audio/webm")}, data={"turn_id": "12345678-1234-1234-1234-123456789012", "response_mode": "text"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeCallUseCase.modes, [ResponseMode.SPEECH])
        self.assertLess(response.text.index("event: answer"), response.text.index("event: audio\n"))
        self.assertIn("event: transcript", response.text)
        self.assertIn("event: done", response.text)
        self.assertFalse(call.active_turns)

    def test_invalid_file_does_not_reach_transcriber(self):
        with patch.object(call, "settings", replace(call.settings, groq_api_key="test-key")), patch.object(call, "voice_service", FakePocketTTS()), patch.object(GroqTranscriber, "transcribe", AsyncMock()) as transcribe:
            response = self.client.post("/call/stream", files={"audio": ("fake.webm", b"plain text", "audio/webm")}, data={"turn_id": "12345678-1234-1234-1234-123456789012"})
        self.assertEqual(response.status_code, 400)
        transcribe.assert_not_called()

    def test_signed_in_call_uses_temporary_context_even_with_conversation_id(self):
        self.app.dependency_overrides[optional_current_user] = lambda: SimpleNamespace(id="signed001")
        with patch.object(call, "settings", replace(call.settings, groq_api_key="test-key")), patch.object(call, "voice_service", FakePocketTTS()), patch.object(GroqTranscriber, "transcribe", AsyncMock(return_value="Outra pergunta")):
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
