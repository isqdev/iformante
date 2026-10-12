from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.rag.models import ModelMessage

from app.prompts import PROMPT_DEFAULTS

SYSTEM_PROMPT = PROMPT_DEFAULTS["prompt_router"]

class BuscarDocumentos(BaseModel):
    model_config = ConfigDict(title="buscar_documentos")
    query: str = Field(
        description=(
            "Um único parágrafo curto para recuperação: HyDE declarativo para "
            "conteúdo descritivo ou representação de cabeçalho/catálogo para "
            "listas e tabelas, sem inventar itens ou valores."
        ),
    )
    user_question: str = Field(description="Pergunta reescrita, completa e autossuficiente.")


@dataclass(frozen=True)
class QuestionRouteResult:
    direct_response: str | None
    query: str | None
    user_question: str


class QuestionRouter:
    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._chat_model: ChatOpenAI | None = None

    @property
    def is_configured(self) -> bool:
        return self._api_key is not None

    def warm_up(self) -> None:
        self._get_chat_model()

    async def execute(self, messages: list[ModelMessage], *, system_prompt: str = SYSTEM_PROMPT) -> QuestionRouteResult:
        valid = [message for message in messages if message.content.strip()]
        if not valid:
            raise ValueError("Nenhuma mensagem valida foi enviada.")
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")
        response = await self._get_chat_model().ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="\n".join(f"{item.role}: {item.content}" for item in valid)),
        ])
        tool = next((call for call in (response.tool_calls or []) if call.get("name") in {"BuscarDocumentos", "buscar_documentos"}), None)
        if not tool:
            return QuestionRouteResult(
                self._text(response.content).strip() or "Olá! Como posso ajudar?",
                None,
                valid[-1].content,
            )
        args = tool.get("args") or {}
        query = str(args.get("query") or "").strip()
        question = str(args.get("user_question") or "").strip()
        if not query or not question:
            raise ValueError("A tool buscar_documentos deve informar query e user_question.")
        return QuestionRouteResult(None, query, question)

    def _get_chat_model(self) -> ChatOpenAI:
        if self._chat_model is None:
            self._chat_model = ChatOpenAI(
                api_key=self._api_key,
                model=self._model,
                temperature=0,
            ).bind_tools([BuscarDocumentos])
        return self._chat_model

    def _text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        return "".join(item.get("text", "") for item in content if isinstance(item, dict)) if isinstance(content, list) else ""
