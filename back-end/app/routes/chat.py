import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.factories.chat import get_receive_message_use_case
from app.models import User
from app.security.dependencies import optional_current_user
from app.rag.models import ModelMessage
from app.dtos import SendMessageRequest
from app.use_cases import ReceiveMessageUseCase

ANONYMOUS_COOKIE_NAME = "iformante_anonymous_id"

router = APIRouter()


def format_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def send_message(
    payload: SendMessageRequest,
    user: Annotated[User | None, Depends(optional_current_user)],
    receive_message_use_case: Annotated[
        ReceiveMessageUseCase,
        Depends(get_receive_message_use_case),
    ],
) -> StreamingResponse:
    message = payload.sanitized_message()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma mensagem valida foi enviada.",
        )

    if not receive_message_use_case.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY nao configurada no back-end.",
        )

    history = list(payload.messages or [])
    if history and history[-1].role == "user" and history[-1].content.strip() == message:
        history.pop()

    async def stream_response() -> AsyncIterator[str]:
        async for event in receive_message_use_case.stream(
            conversation_id=payload.conversation_id,
            anonymous_id=None,
            message=message,
            user_id=user.id if user else None,
            history=[ModelMessage(role=item.role, content=item.content) for item in history[-30:]],
        ):
            yield format_sse(
                event.event,
                event.payload,
            )

    response = StreamingResponse(
        stream_response(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


    return response
