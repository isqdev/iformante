from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from app.factories.chat import (
    get_get_conversation_use_case,
    get_list_conversations_use_case,
)
from app.models import Message, MessageAuthor, User
from app.security.dependencies import require_user
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
    user: Annotated[User, Depends(require_user)],
    use_case: Annotated[
        ListConversationsUseCase,
        Depends(get_list_conversations_use_case),
    ],
) -> list[ConversationSummaryResponse]:
    conversations = await use_case.execute(user.id)

    return [
        ConversationSummaryResponse(
            id=conversation.id,
            title=conversation.title,
            channel=conversation.channel or "text",
        )
        for conversation in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    user: Annotated[User, Depends(require_user)],
    use_case: Annotated[
        GetConversationUseCase,
        Depends(get_get_conversation_use_case),
    ],
) -> ConversationResponse:
    result = await use_case.execute(
        conversation_id,
        user.id,
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
        channel=conversation.channel or "text",
        messages=[
            MessageResponse(
                id=message.id,
                role="assistant" if message.author == MessageAuthor.AI.value else "user",
                content=message.content,
                response_mode=message.response_mode or "text",
                playback_status=message.playback_status,
                sources=_message_sources(message),
            )
            for message in messages
        ],
    )


def _message_sources(message: Message) -> list[MessageSourceResponse]:
    from app.services.citations import group_citations
    return [MessageSourceResponse(**item) for item in group_citations([
        {"document_id": s.document_id, "filename": (s.document.file_name or s.document.title).strip(), "url": s.document.source_url, "source_type": s.document.source_type, "chunk_id": s.chunk_id, "bbox": s.bbox}
        for s in message.sources if s.document.ingestion_status == "INDEXED"
    ])]
