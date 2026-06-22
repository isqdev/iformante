from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.use_cases.chat import (
    ConversationManager,
    ReceiveMessageUseCase,
    ReplyMessageUseCase,
    RouteOrRetrieveMessageUseCase,
)


@lru_cache(maxsize=1)
def get_route_or_retrieve_message_use_case() -> RouteOrRetrieveMessageUseCase:
    return RouteOrRetrieveMessageUseCase(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        top_k=settings.rag_top_k,
    )


@lru_cache(maxsize=1)
def get_reply_message_use_case() -> ReplyMessageUseCase:
    return ReplyMessageUseCase(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


def get_conversation_manager(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ConversationManager:
    return ConversationManager(session)


def get_receive_message_use_case(
    conversation_manager: Annotated[
        ConversationManager,
        Depends(get_conversation_manager),
    ],
    route_use_case: Annotated[
        RouteOrRetrieveMessageUseCase,
        Depends(get_route_or_retrieve_message_use_case),
    ],
    reply_use_case: Annotated[
        ReplyMessageUseCase,
        Depends(get_reply_message_use_case),
    ],
) -> ReceiveMessageUseCase:
    return ReceiveMessageUseCase(
        conversation_manager=conversation_manager,
        route_or_retrieve_message_use_case=route_use_case,
        reply_message_use_case=reply_use_case,
        history_limit=settings.chat_history_limit,
    )
