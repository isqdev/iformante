import json
import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.domains.chat import ChatDomain
from app.domains.conversation import ConversationDomain
from app.models import MessageAuthor, generate_id
from model.chat import ChatMessage, SendMessageRequest

ANONYMOUS_COOKIE_NAME = "iformante_anonymous_id"

router = APIRouter()
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_chat_domain() -> ChatDomain:
    return ChatDomain(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        top_k=settings.rag_top_k,
    )


def get_conversation_domain(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ConversationDomain:
    return ConversationDomain(session)


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
    chat_domain: Annotated[ChatDomain, Depends(get_chat_domain)],
    conversation_domain: Annotated[ConversationDomain, Depends(get_conversation_domain)],
) -> StreamingResponse:
    message = payload.sanitized_message()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma mensagem valida foi enviada.",
        )

    if not chat_domain.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY nao configurada no back-end.",
        )

    anonymous_id, should_set_cookie = get_or_create_anonymous_id(request)

    async def stream_response() -> AsyncIterator[str]:
        assistant_content = ""
        started_at = perf_counter()
        first_token_logged = False

        try:
            conversation = await conversation_domain.create_or_get_conversation(
                payload.conversation_id,
                anonymous_id,
                message,
            )
            previous_messages = await conversation_domain.list_recent_messages(
                conversation.id,
                settings.chat_history_limit,
            )
            user_message = await conversation_domain.create_user_message(
                conversation.id,
                message,
            )
            await conversation_domain.touch_conversation(conversation)
            await conversation_domain.commit()
            logger.info(
                "chat.db_elapsed_ms=%s conversation_id=%s",
                round((perf_counter() - started_at) * 1000),
                conversation.id,
            )

            yield format_sse(
                "conversation",
                {
                    "conversation_id": conversation.id,
                    "title": conversation.title,
                    "message_id": user_message.id,
                },
            )

            model_messages = [
                ChatMessage(
                    role="assistant" if item.author == MessageAuthor.AI.value else "user",
                    content=item.content,
                )
                for item in previous_messages
            ]
            model_messages.append(ChatMessage(role="user", content=message))

            async for chunk in chat_domain.stream_response(model_messages):
                if not first_token_logged:
                    first_token_logged = True
                    logger.info(
                        "chat.first_token_elapsed_ms=%s conversation_id=%s",
                        round((perf_counter() - started_at) * 1000),
                        conversation.id,
                    )
                assistant_content += chunk
                yield format_sse("delta", {"content": chunk})

            assistant_message = await conversation_domain.create_assistant_message(
                conversation.id,
                assistant_content,
            )
            await conversation_domain.touch_conversation(conversation)
            await conversation_domain.commit()
            logger.info(
                "chat.total_elapsed_ms=%s conversation_id=%s",
                round((perf_counter() - started_at) * 1000),
                conversation.id,
            )
            yield format_sse(
                "done",
                {
                    "message_id": assistant_message.id,
                },
            )
        except ValueError as error:
            await conversation_domain.rollback()
            yield format_sse("error", {"message": str(error)})
        except RuntimeError as error:
            await conversation_domain.rollback()
            yield format_sse("error", {"message": str(error)})
        except Exception:
            await conversation_domain.rollback()
            yield format_sse(
                "error",
                {"message": "Nao foi possivel gerar a resposta da IA."},
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
