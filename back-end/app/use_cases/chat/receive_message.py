import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.models import MessageAuthor
from app.schemas.chat import ChatMessage

from .conversation_manager import ConversationManager
from .reply_message import ReplyMessageUseCase
from .route_or_retrieve_message import RouteOrRetrieveMessageUseCase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatStreamEvent:
    event: str
    payload: dict[str, Any]


class ReceiveMessageUseCase:
    def __init__(
        self,
        conversation_manager: ConversationManager,
        route_or_retrieve_message_use_case: RouteOrRetrieveMessageUseCase,
        reply_message_use_case: ReplyMessageUseCase,
        history_limit: int,
    ) -> None:
        self._conversation_manager = conversation_manager
        self._route_or_retrieve_message_use_case = route_or_retrieve_message_use_case
        self._reply_message_use_case = reply_message_use_case
        self._history_limit = history_limit

    @property
    def is_configured(self) -> bool:
        return (
            self._route_or_retrieve_message_use_case.is_configured
            and self._reply_message_use_case.is_configured
        )

    async def stream(
        self,
        conversation_id: str | None,
        anonymous_id: str,
        message: str,
    ) -> AsyncIterator[ChatStreamEvent]:
        assistant_content = ""
        sources: list[dict[str, str]] = []
        started_at = perf_counter()
        first_token_logged = False

        try:
            conversation = await self._conversation_manager.create_or_get_conversation(
                conversation_id,
                anonymous_id,
                message,
            )
            previous_messages = await self._conversation_manager.list_recent_messages(
                conversation.id,
                self._history_limit,
            )
            user_message = await self._conversation_manager.create_user_message(
                conversation.id,
                message,
            )
            await self._conversation_manager.touch_conversation(conversation)
            await self._conversation_manager.commit()
            logger.info(
                "chat.db_elapsed_ms=%s conversation_id=%s",
                round((perf_counter() - started_at) * 1000),
                conversation.id,
            )

            yield ChatStreamEvent(
                "conversation",
                {
                    "conversation_id": conversation.id,
                    "title": conversation.title,
                    "message_id": user_message.id,
                },
            )

            model_messages = self._build_model_messages(previous_messages, message)
            route_result = await self._route_or_retrieve_message_use_case.execute(
                model_messages[-5:],
            )

            if route_result.direct_response is not None:
                assistant_content = route_result.direct_response
                yield ChatStreamEvent("delta", {"content": assistant_content})
            else:
                sources = self._build_sources(route_result.documents)

                async for chunk in self._reply_message_use_case.stream(
                    route_result.user_question,
                    route_result.documents,
                ):
                    if not first_token_logged:
                        first_token_logged = True
                        logger.info(
                            "chat.first_token_elapsed_ms=%s conversation_id=%s",
                            round((perf_counter() - started_at) * 1000),
                            conversation.id,
                        )

                    assistant_content += chunk
                    yield ChatStreamEvent("delta", {"content": chunk})

            assistant_message = await self._conversation_manager.create_assistant_message(
                conversation.id,
                assistant_content,
            )
            await self._conversation_manager.touch_conversation(conversation)
            await self._conversation_manager.commit()
            logger.info(
                "chat.total_elapsed_ms=%s conversation_id=%s",
                round((perf_counter() - started_at) * 1000),
                conversation.id,
            )
            yield ChatStreamEvent(
                "done",
                {
                    "message_id": assistant_message.id,
                    "sources": sources,
                },
            )
        except ValueError as error:
            await self._conversation_manager.rollback()
            yield ChatStreamEvent("error", {"message": str(error)})
        except RuntimeError as error:
            await self._conversation_manager.rollback()
            yield ChatStreamEvent("error", {"message": str(error)})
        except Exception:
            logger.exception("chat.unhandled_error")
            await self._conversation_manager.rollback()
            yield ChatStreamEvent(
                "error",
                {"message": "Nao foi possivel gerar a resposta da IA."},
            )

    def _build_model_messages(
        self,
        previous_messages: list[Any],
        current_message: str,
    ) -> list[ChatMessage]:
        model_messages = [
            ChatMessage(
                role="assistant" if item.author == MessageAuthor.AI.value else "user",
                content=item.content,
            )
            for item in previous_messages
        ]
        model_messages.append(ChatMessage(role="user", content=current_message))
        return model_messages

    def _build_sources(self, documents: list[Any]) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        seen_keys: set[str] = set()

        for document in documents:
            metadata = document.metadata
            url = str(metadata.get("source_url") or "").strip()
            filename = str(
                metadata.get("filename")
                or metadata.get("title")
                or metadata.get("document_id")
                or "Documento",
            ).strip()
            source_key = url

            if not url or source_key in seen_keys:
                continue

            seen_keys.add(source_key)
            sources.append(
                {
                    "filename": filename,
                    "url": url,
                },
            )

        return sources
