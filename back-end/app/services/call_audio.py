import asyncio
import base64
import logging
import multiprocessing as mp
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from app.services.speech_text import within_speech_budget

logger = logging.getLogger(__name__)
MAX_AUDIO_BYTES = 10 * 1024 * 1024


def audio_extension(data: bytes) -> str:
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    if data.startswith(b"OggS"):
        return "ogg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "wav"
    if data[4:8] == b"ftyp":
        return "mp4"
    raise ValueError("O arquivo enviado não contém um áudio compatível.")


class GroqTranscriber:
    def __init__(self, api_key: str | None):
        self.api_key = api_key

    async def transcribe(self, data: bytes) -> str:
        if not self.api_key:
            raise RuntimeError("A transcrição está indisponível. Configure a chave da Groq no servidor.")
        if not data or len(data) > MAX_AUDIO_BYTES:
            raise ValueError("Envie uma gravação com até 10 MB.")
        extension = audio_extension(data)
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={"model": "whisper-large-v3-turbo", "language": "pt", "response_format": "verbose_json", "temperature": "0"},
                    files={"file": (f"recording.{extension}", data)},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("call.transcription_failed type=%s", type(error).__name__)
            raise RuntimeError("Não foi possível transcrever o áudio. Tente novamente.") from error
        segments = payload.get("segments") or []
        if segments and all(segment.get("no_speech_prob", 0) >= 0.8 for segment in segments):
            raise ValueError("Nenhuma fala foi identificada. Segure para falar novamente.")
        text = str(payload.get("text") or "").strip()
        if not text:
            raise ValueError("Nenhuma fala foi identificada. Segure para falar novamente.")
        return text


def _piper_worker(connection, model_path: str):
    """One loaded voice per worker. Terminating a worker also stops ONNX inference."""
    try:
        from piper import PiperVoice
        voice = PiperVoice.load(model_path, include_alignments=True)
        connection.send(("ready", {}))
        while True:
            text = connection.recv()
            if text is None:
                return
            offset = 0
            sequence = 0
            for chunk in voice.synthesize(text, include_alignments=True):
                rate = chunk.sample_rate
                connection.send(("audio_format", {"sample_rate": rate, "channels": chunk.sample_channels, "sample_width": chunk.sample_width}))
                alignments = []
                cursor = offset
                for alignment in chunk.phoneme_alignments or []:
                    alignments.append({"phoneme": alignment.phoneme, "start": cursor / rate, "duration": alignment.num_samples / rate})
                    cursor += alignment.num_samples
                if alignments:
                    connection.send(("alignment", {"items": alignments}))
                raw = chunk.audio_int16_bytes
                # Small transport frames provide backpressure and responsive interruption.
                frame_bytes = max(2, int(rate * 0.1) * 2)
                for start in range(0, len(raw), frame_bytes):
                    frame = raw[start:start + frame_bytes]
                    connection.send(("audio", {"sequence": sequence, "data": base64.b64encode(frame).decode("ascii")}))
                    sequence += 1
                offset += len(raw) // 2
            connection.send(("audio_done", {"samples": offset}))
    except (EOFError, BrokenPipeError):
        pass
    except Exception:
        logger.exception("call.piper_worker_failed")
        try:
            connection.send(("error", {"message": "Não foi possível gerar a voz do InFormante."}))
        except (EOFError, BrokenPipeError):
            pass
    finally:
        connection.close()


class PiperService:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._lock = asyncio.Lock()
        self._process = None
        self._connection = None
        self._ready = False

    @property
    def configured(self) -> bool:
        return Path(self.model_path).is_file() and Path(f"{self.model_path}.json").is_file()

    def _start(self):
        if not self.configured:
            raise RuntimeError("A voz do InFormante ainda não foi instalada no servidor.")
        context = mp.get_context("spawn")
        parent, child = context.Pipe()
        self._process = context.Process(target=_piper_worker, args=(child, self.model_path), daemon=True)
        self._process.start()
        child.close()
        self._connection = parent
        self._ready = False

    async def _receive(self):
        while True:
            if self._connection and self._connection.poll():
                return self._connection.recv()
            if not self._process or not self._process.is_alive():
                raise RuntimeError("A voz está indisponível. Tente novamente.")
            await asyncio.sleep(0.02)

    async def warm_up(self):
        async with self._lock:
            if self._process and self._process.is_alive() and self._ready:
                return
            self._start()
            event, payload = await self._receive()
            if event != "ready":
                await self.close()
                raise RuntimeError(payload.get("message", "Não foi possível carregar a voz."))
            self._ready = True

    async def stream(self, text: str) -> AsyncIterator[tuple[str, dict]]:
        if not within_speech_budget(text):
            raise ValueError("A resposta excedeu o limite de palavras para a chamada.")
        completed = False
        async with self._lock:
            try:
                if not self._process or not self._process.is_alive():
                    self._start()
                if not self._ready:
                    event, payload = await self._receive()
                    if event != "ready":
                        raise RuntimeError(payload.get("message", "Não foi possível carregar a voz."))
                    self._ready = True
                self._connection.send(text)
                while True:
                    event, payload = await self._receive()
                    if event == "error":
                        raise RuntimeError(payload["message"])
                    if event == "audio_done":
                        completed = True
                        yield event, payload
                        return
                    yield event, payload
            finally:
                if not completed:
                    await self.close()

    async def close(self):
        process, self._process = self._process, None
        connection, self._connection = self._connection, None
        self._ready = False
        if connection:
            connection.close()
        if process:
            if process.is_alive():
                process.terminate()
            await asyncio.to_thread(process.join, 3)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join, 1)
