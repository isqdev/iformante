from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_database_session
from app.domains.conversation import ConversationDomain
from app.models import MessageAuthor
from app.routes.chat import get_or_create_anonymous_id, set_anonymous_cookie
from model.conversation import (
    ConversationResponse,
    ConversationSummaryResponse,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_domain(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ConversationDomain:
    return ConversationDomain(session)


@router.get("", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    request: Request,
    response: Response,
    conversation_domain: Annotated[ConversationDomain, Depends(get_conversation_domain)],
) -> list[ConversationSummaryResponse]:
    anonymous_id, should_set_cookie = get_or_create_anonymous_id(request)

    if should_set_cookie:
        set_anonymous_cookie(response, anonymous_id, request)

    conversations = await conversation_domain.list_conversations(anonymous_id)

    return [
        ConversationSummaryResponse(
            id=conversation.id,
            title=conversation.title,
        )
        for conversation in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    request: Request,
    response: Response,
    conversation_domain: Annotated[ConversationDomain, Depends(get_conversation_domain)],
) -> ConversationResponse:
    anonymous_id, should_set_cookie = get_or_create_anonymous_id(request)

    if should_set_cookie:
        set_anonymous_cookie(response, anonymous_id, request)

    conversation = await conversation_domain.get_conversation(
        conversation_id,
        anonymous_id,
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa nao encontrada.",
        )

    messages = await conversation_domain.list_messages(conversation.id)

    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        messages=[
            MessageResponse(
                id=message.id,
                role="assistant" if message.author == MessageAuthor.AI.value else "user",
                content=message.content,
            )
            for message in messages
        ],
    )
