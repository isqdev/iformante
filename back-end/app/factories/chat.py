from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_database_session
from app.factories.rag import (
    get_answer_generator,
    get_question_router,
)
from app.repositories import (
    ConversationRepository,
    MessageRepository,
    MessageSourceRepository,
    RagRepository,
    RagRetrievalAuditRepository,
)
from app.repositories import UnitOfWork
from app.repositories.system_param_repository import SystemParamRepository
from app.security.auth import AuthError
from app.rag.generation import AnswerGenerator, QuestionRouter
from app.rag.retrieval import ParentRetriever
from app.use_cases.conversations import GetConversationUseCase, ListConversationsUseCase
from app.use_cases.chat import (
    ReceiveMessageUseCase,
)


def get_list_conversations_use_case(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ListConversationsUseCase:
    return ListConversationsUseCase(ConversationRepository(session))


def get_get_conversation_use_case(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> GetConversationUseCase:
    return GetConversationUseCase(
        conversation_repository=ConversationRepository(session),
        message_repository=MessageRepository(session),
    )


async def get_receive_message_use_case(
    session: Annotated[AsyncSession, Depends(get_database_session)],
    route_use_case: Annotated[
        QuestionRouter,
        Depends(get_question_router),
    ],
    reply_use_case: Annotated[
        AnswerGenerator,
        Depends(get_answer_generator),
    ],
) -> ReceiveMessageUseCase:
    try:
        prompts = await SystemParamRepository(session).snapshot()
    except (KeyError, ValueError) as error:
        raise AuthError("Prompts do sistema não configurados. Aplique a migração do banco.", 503) from error
    return ReceiveMessageUseCase(
        conversation_repository=ConversationRepository(session),
        message_repository=MessageRepository(session),
        unit_of_work=UnitOfWork(session),
        question_router=route_use_case,
        answer_generator=reply_use_case,
        parent_retriever=ParentRetriever(
            settings.openai_api_key,
            settings.openai_embedding_model,
            settings.rag_top_k,
            RagRepository(session),
            settings.rag_reranker_model,
            settings.rag_candidate_count,
            prompts.reranker,
        ),
        message_source_repository=MessageSourceRepository(session),
        rag_retrieval_audit_repository=RagRetrievalAuditRepository(session),
        prompts=prompts,
    )
