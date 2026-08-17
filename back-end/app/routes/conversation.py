from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from app.factories.chat import (
    get_get_conversation_use_case,
    get_list_conversations_use_case,
)
from app.models import Message, MessageAuthor
from app.routes.chat import get_or_create_anonymous_id, set_anonymous_cookie
from app.dtos import (
    ConversationResponse,
    ConversationSummaryResponse,
    MessageResponse,
    MessageSourceResponse,
)
from app.use_cases.conversations import GetConversationUseCase, ListConversationsUseCase

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    request: Request,
    response: Response,
    use_case: Annotated[
        ListConversationsUseCase,
        Depends(get_list_conversations_use_case),
    ],
) -> list[ConversationSummaryResponse]:
    anonymous_id, should_set_cookie = get_or_create_anonymous_id(request)

    if should_set_cookie:
        set_anonymous_cookie(response, anonymous_id, request)

    conversations = await use_case.execute(anonymous_id)

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
    use_case: Annotated[
        GetConversationUseCase,
        Depends(get_get_conversation_use_case),
    ],
) -> ConversationResponse:
    anonymous_id, should_set_cookie = get_or_create_anonymous_id(request)

    if should_set_cookie:
        set_anonymous_cookie(response, anonymous_id, request)

    result = await use_case.execute(
        conversation_id,
        anonymous_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa nao encontrada.",
        )

    conversation = result.conversation
    messages = result.messages

    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        messages=[
            MessageResponse(
                id=message.id,
                role="assistant" if message.author == MessageAuthor.AI.value else "user",
                content=message.content,
                sources=_message_sources(message),
            )
            for message in messages
        ],
    )


def _message_sources(message: Message) -> list[MessageSourceResponse]:
    sources: list[MessageSourceResponse] = []
    seen_urls: set[str] = set()
    for source in message.sources:
        url = source.document.source_url.strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append(
            MessageSourceResponse(
                document_id=source.document_id,
                filename=(source.document.file_name or source.document.title).strip(),
                url=url,
            ),
        )
    return sources
