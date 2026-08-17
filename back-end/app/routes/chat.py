import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from app.factories.chat import get_receive_message_use_case
from app.models import generate_id
from app.dtos import SendMessageRequest
from app.use_cases import ReceiveMessageUseCase

ANONYMOUS_COOKIE_NAME = "iformante_anonymous_id"

router = APIRouter()


def get_or_create_anonymous_id(request: Request) -> tuple[str, bool]:
    anonymous_id = request.cookies.get(ANONYMOUS_COOKIE_NAME)

    if anonymous_id:
        return anonymous_id, False

    return generate_id(), True


def set_anonymous_cookie(
    response: Response,
    anonymous_id: str,
    request: Request,
) -> None:
    response.set_cookie(
        key=ANONYMOUS_COOKIE_NAME,
        value=anonymous_id,
        max_age=60 * 60 * 24 * 180,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )


def format_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def send_message(
    payload: SendMessageRequest,
    request: Request,
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

    anonymous_id, should_set_cookie = get_or_create_anonymous_id(request)

    async def stream_response() -> AsyncIterator[str]:
        async for event in receive_message_use_case.stream(
            conversation_id=payload.conversation_id,
            anonymous_id=anonymous_id,
            message=message,
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

    if should_set_cookie:
        set_anonymous_cookie(response, anonymous_id, request)

    return response
