import asyncio
import json
import logging
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.config import settings
from app.dtos.chat import ChatMessage
from app.factories.chat import get_receive_message_use_case
from app.models import User
from app.rag.models import ModelMessage
from app.routes.chat import format_sse
from app.security.dependencies import optional_current_user
from app.services.call_audio import GroqTranscriber, MAX_AUDIO_BYTES, PocketTTSService, audio_extension
from app.services.speech_text import ResponseMode
from app.use_cases.chat import ReceiveMessageUseCase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/call", tags=["call"])
voice_service = PocketTTSService(settings.pocket_tts_config_path, settings.pocket_tts_voice_path)


@dataclass
class ActiveTurn:
    owner: str | None
    task: asyncio.Task | None = None
    cancelled: bool = False


# A single API process owns the voice worker. See CALL.md for scaling to more replicas.
active_turns: dict[str, ActiveTurn] = {}


class CancelRequest(BaseModel):
    turn_id: str = Field(min_length=36, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")


class PlaybackRequest(BaseModel):
    message_id: str = Field(min_length=9, max_length=9)
    status: Literal["completed", "interrupted", "failed"]


@router.get("/status")
async def call_status():
    return {"ready": bool(settings.groq_api_key) and bool(settings.openai_api_key) and voice_service.configured,
            "transcription_ready": bool(settings.groq_api_key), "voice_ready": voice_service.configured,
            "answer_ready": bool(settings.openai_api_key)}


@router.post("/cancel")
async def cancel_turn(payload: CancelRequest, user: Annotated[User | None, Depends(optional_current_user)]):
    turn = active_turns.get(payload.turn_id)
    if turn and turn.owner == (user.id if user else None):
        turn.cancelled = True
        if turn.task:
            turn.task.cancel()
    # The random turn id is a capability for anonymous calls; do not reveal other turns.
    return {"cancelled": True}


@router.post("/playback")
async def playback_status(payload: PlaybackRequest):
    # Compatibility for already-open clients; calls never persist playback.
    return {"saved": False}


@router.post("/stream")
async def call_stream(
    request: Request,
    user: Annotated[User | None, Depends(optional_current_user)],
    use_case: Annotated[ReceiveMessageUseCase, Depends(get_receive_message_use_case)],
    audio: Annotated[UploadFile, File()],
    turn_id: Annotated[str, Form()],
    messages: Annotated[str, Form()] = "[]",
):
    if not re.fullmatch(r"[a-zA-Z0-9-]{36,64}", turn_id):
        raise HTTPException(400, "Identificador de chamada inválido.")
    if turn_id in active_turns or len(active_turns) >= 8:
        raise HTTPException(429, "A chamada está ocupada. Tente novamente em instantes.")
    if not (settings.groq_api_key and voice_service.configured and use_case.is_configured):
        raise HTTPException(503, "A chamada ainda não está configurada no servidor.")
    if len(messages) > 100_000:
        raise HTTPException(400, "Histórico muito grande.")
    try:
        history = TypeAdapter(list[ChatMessage]).validate_json(messages)[-30:]
        data = await audio.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "Envie uma gravação com até 10 MB.")
        audio_extension(data)
    except (ValueError, ValidationError) as error:
        raise HTTPException(400, "Gravação ou histórico inválido.") from error
    finally:
        await audio.close()
    owner = user.id if user else None
    turn = ActiveTurn(owner)
    active_turns[turn_id] = turn

    async def stream():
        turn.task = asyncio.current_task()
        monitor = None
        async def watch_disconnect():
            while True:
                if await request.is_disconnected():
                    turn.cancelled = True
                    if turn.task:
                        turn.task.cancel()
                    return
                await asyncio.sleep(0.2)
        try:
            if turn.cancelled:
                return
            monitor = asyncio.create_task(watch_disconnect())
            yield format_sse("state", {"value": "transcribing", "turn_id": turn_id})
            transcript = await GroqTranscriber(settings.groq_api_key).transcribe(data)
            yield format_sse("transcript", {"text": transcript})
            yield format_sse("state", {"value": "thinking"})
            answer = ""
            done = None
            # Every call uses the temporary chat path, including signed-in users.
            # Ownership is retained above only to protect cancellation.
            async for event in use_case.stream(conversation_id=None, anonymous_id=None,
                                              message=transcript, user_id=None,
                                              history=[ModelMessage(role=m.role, content=m.content) for m in history],
                                              response_mode=ResponseMode.SPEECH):
                if event.event == "delta":
                    answer += event.payload.get("content", "")
                elif event.event == "done":
                    done = event.payload
                else:
                    yield format_sse(event.event, event.payload)
                    if event.event == "error":
                        return
            if not done:
                raise RuntimeError("Não foi possível finalizar a resposta.")
            yield format_sse("answer", {"text": answer, **done})
            yield format_sse("state", {"value": "speaking"})
            async for event, payload in voice_service.stream(answer):
                yield format_sse(event, payload)
            yield format_sse("done", done)
        except asyncio.CancelledError:
            raise
        except (RuntimeError, ValueError) as error:
            yield format_sse("error", {"message": str(error)})
        except Exception:
            logger.exception("call.unhandled_error")
            yield format_sse("error", {"message": "Não foi possível concluir a chamada. Tente novamente."})
        finally:
            active_turns.pop(turn_id, None)
            if monitor:
                monitor.cancel()
                with suppress(asyncio.CancelledError):
                    await monitor

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
