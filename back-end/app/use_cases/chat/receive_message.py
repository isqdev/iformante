import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from time import perf_counter
from datetime import UTC, datetime
from app.models import generate_id
from typing import Any
from app.services.speech_text import ResponseMode

from app.models import (
    Conversation,
    Message,
    MessageAuthor,
    MessageSource,
    RagRetrievalAudit,
)
from app.rag.generation import AnswerDelta, AnswerGenerator, AnswerResult, QuestionRouter
from app.rag.models import ModelMessage
from app.rag.retrieval import (
    ParentRetrievalResult,
    ParentRetriever,
    RetrievedParent,
)
from app.repositories import (
    ConversationRepository,
    MessageRepository,
    MessageSourceRepository,
    RagRetrievalAuditRepository,
    UnitOfWork,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatStreamEvent:
    event: str
    payload: dict[str, Any]


class ReceiveMessageUseCase:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        unit_of_work: UnitOfWork,
        question_router: QuestionRouter,
        answer_generator: AnswerGenerator,
        parent_retriever: ParentRetriever,
        message_source_repository: MessageSourceRepository,
        rag_retrieval_audit_repository: RagRetrievalAuditRepository,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._message_repository = message_repository
        self._unit_of_work = unit_of_work
        self._question_router = question_router
        self._answer_generator = answer_generator
        self._parent_retriever = parent_retriever
        self._message_source_repository = message_source_repository
        self._rag_retrieval_audit_repository = rag_retrieval_audit_repository

    @property
    def is_configured(self) -> bool:
        return (
            self._question_router.is_configured
            and self._answer_generator.is_configured
        )

    async def stream(
        self,
        conversation_id: str | None,
        anonymous_id: str | None,
        message: str,
        user_id: str | None = None,
        history: list[ModelMessage] | None = None,
        response_mode: ResponseMode = ResponseMode.TEXT,
    ) -> AsyncIterator[ChatStreamEvent]:
        assistant_content = ""
        sources: list[dict[str, Any]] = []
        retrieval: ParentRetrievalResult | None = None
        router_task: asyncio.Task | None = None
        started_at = perf_counter()

        try:
            conversation = None
            if user_id:
                conversation = await self._create_or_get_conversation(conversation_id, user_id, message)
                if response_mode == ResponseMode.SPEECH:
                    conversation.channel = "speech"
                previous_messages = await self._message_repository.list_model_history(conversation.id)
                user_message = await self._message_repository.create(Message.from_user(conversation.id, message))
                conversation.touch()
                model_messages = self._build_model_messages(previous_messages, message)
                await self._unit_of_work.commit()
                yield ChatStreamEvent("conversation", {"conversation_id": conversation.id, "title": conversation.title, "message_id": user_message.id})
            else:
                model_messages = [*(history or [])[-30:], ModelMessage(role="user", content=message)]
            router_task = asyncio.create_task(self._execute_router_with_timing(model_messages))

            route_result = await router_task
            uses_rag = route_result.direct_response is None
            yield ChatStreamEvent(
                "rag",
                {"active": uses_rag},
            )

            if route_result.direct_response is not None:
                assistant_content = route_result.direct_response
                if response_mode == ResponseMode.SPEECH:
                    assistant_content = await self._answer_generator.prepare_direct_speech(assistant_content)
                yield ChatStreamEvent(
                    "delta",
                    {"content": assistant_content},
                )
            else:
                print(
                    f"[RAG] Query reescrita pelo LLM: {route_result.query}",
                    flush=True,
                )
                retrieval_started_at = perf_counter()
                retrieval = await self._parent_retriever.retrieve(
                    route_result.query or "",
                )
                self._print_timing("retrieval_total", retrieval_started_at)
                parents = retrieval.parents

                result: AnswerResult | None = None
                replier_started_at = perf_counter()
                first_delta_received = False
                async def answer_events():
                    if response_mode == ResponseMode.SPEECH:
                        answer = await self._answer_generator.speech_answer(route_result.user_question, parents)
                        yield AnswerDelta(answer.content)
                        yield answer
                    else:
                        async for event in self._answer_generator.stream(route_result.user_question, parents):
                            yield event

                async for answer_event in answer_events():
                    if isinstance(answer_event, AnswerDelta):
                        if not first_delta_received:
                            first_delta_received = True
                            self._print_timing(
                                "replier_ttft",
                                replier_started_at,
                            )
                        yield ChatStreamEvent(
                            "delta",
                            {"content": answer_event.content},
                        )
                    else:
                        result = answer_event
                if result is None:
                    raise RuntimeError("A IA nao finalizou a resposta.")
                self._print_timing("replier_total", replier_started_at)
                assistant_content = result.content
                sources = self._build_sources(parents, result.used_parent_ids)

            assistant_id = generate_id()
            if conversation is not None:
                assistant_message = await self._message_repository.create(Message.from_assistant(conversation.id, assistant_content))
                assistant_message.response_mode = response_mode.value
                if response_mode == ResponseMode.SPEECH:
                    assistant_message.playback_status = "pending"
                assistant_id = assistant_message.id
                if route_result.direct_response is None:
                    await self._persist_sources(assistant_id, parents, result.used_parent_ids)
                    await self._persist_retrieval_audit(assistant_id, route_result.query or "", retrieval, result.used_parent_ids)
                conversation.touch()
                await self._unit_of_work.commit()
            yield ChatStreamEvent(
                "done",
                {
                    "message_id": assistant_id,
                    "sources": sources,
                },
            )
        except ValueError as error:
            await self._unit_of_work.rollback()
            yield ChatStreamEvent("error", {"message": str(error)})
        except RuntimeError as error:
            await self._unit_of_work.rollback()
            yield ChatStreamEvent("error", {"message": str(error)})
        except Exception:
            logger.exception("chat.unhandled_error")
            await self._unit_of_work.rollback()
            yield ChatStreamEvent(
                "error",
                {"message": "Nao foi possivel gerar a resposta da IA."},
            )
        finally:
            if router_task is not None and not router_task.done():
                router_task.cancel()
                with suppress(asyncio.CancelledError):
                    await router_task

    async def update_playback(self, message_id: str, user_id: str, playback_status: str) -> None:
        message = await self._message_repository.get_by_id(message_id)
        if not message or message.response_mode != "speech":
            raise ValueError("Resposta de chamada não encontrada.")
        conversation = await self._conversation_repository.get_by_id(message.conversation_id)
        if not conversation or conversation.user_id != user_id or conversation.expires_at <= datetime.now(UTC):
            raise ValueError("Conversa não encontrada.")
        message.playback_status = playback_status
        await self._unit_of_work.commit()

    async def _create_or_get_conversation(
        self,
        conversation_id: str | None,
        user_id: str,
        first_message: str,
    ) -> Conversation:
        if conversation_id:
            conversation = await self._conversation_repository.get_by_id(conversation_id)

            if not conversation or conversation.user_id != user_id or conversation.expires_at <= datetime.now(UTC):
                raise ValueError("Conversa nao encontrada.")

            return conversation

        conversation = Conversation(user_id=user_id, anonymous_id=None, title=Conversation._build_title(first_message))
        await self._conversation_repository.create(conversation)
        return conversation

    def _build_model_messages(
        self,
        previous_messages: list[Any],
        current_message: str,
    ) -> list[ModelMessage]:
        model_messages = [
            ModelMessage(
                role="assistant" if item.author == MessageAuthor.AI.value else "user",
                content=item.content + ("\n[A leitura desta resposta não foi concluída pelo usuário.]" if getattr(item, "playback_status", None) in {"interrupted", "failed", "pending"} else ""),
            )
            for item in previous_messages
        ]
        model_messages.append(ModelMessage(role="user", content=current_message))
        return model_messages

    async def _execute_router_with_timing(
        self,
        model_messages: list[ModelMessage],
    ):
        started_at = perf_counter()
        try:
            return await self._question_router.execute(model_messages)
        finally:
            self._print_timing("router", started_at)

    def _print_timing(self, stage: str, started_at: float) -> None:
        elapsed_ms = (perf_counter() - started_at) * 1000
        print(f"[CHAT] {stage}_elapsed_ms={elapsed_ms:.2f}", flush=True)

    async def _persist_sources(self, message_id: str, parents: list[RetrievedParent], used_ids: list[str]) -> None:
        selected = [parent for parent in parents if parent.id in set(used_ids)]
        await self._message_source_repository.create_many([
            MessageSource(message_id=message_id, document_id=parent.document_id, chunk_id=parent.id, bbox=parent.bbox, rank=index)
            for index, parent in enumerate(selected, start=1)
        ])

    def _build_sources(self, parents: list[RetrievedParent], used_ids: list[str]) -> list[dict]:
        from app.services.citations import group_citations
        return group_citations([{"document_id": p.document_id, "filename": p.filename.strip(), "url": p.source_url, "source_type": p.source_type, "chunk_id": p.id, "bbox": p.bbox} for p in parents if p.id in used_ids])

    async def _persist_retrieval_audit(
        self,
        message_id: str,
        query: str,
        retrieval: ParentRetrievalResult,
        used_parent_ids: list[str],
    ) -> None:
        used_ids = set(used_parent_ids)
        await self._rag_retrieval_audit_repository.create(
            RagRetrievalAudit(
                message_id=message_id,
                rewritten_query=query,
                retrieved_children=[
                    {
                        "child_id": child.child_id,
                        "parent_id": child.parent_id,
                        "vector_rank": child.vector_rank,
                        "vector_score": child.vector_score,
                        "rerank_rank": child.rerank_rank,
                    }
                    for child in retrieval.children
                ],
                retrieved_parents=[
                    {
                        "parent_id": parent.id,
                        "rank": rank,
                        "best_child_id": retrieval.best_child_by_parent.get(
                            parent.id,
                        ),
                        "used": parent.id in used_ids,
                    }
                    for rank, parent in enumerate(retrieval.parents, start=1)
                ],
            ),
        )
