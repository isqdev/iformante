import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.db import build_qdrant_retriever
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
## Contexto

Você é o IFormante, assistente acadêmico oficial do IFPR Campus Paranavaí.
O IFPR (Instituto Federal de Educação, Ciência e Tecnologia do Paraná) é uma instituição
pública federal de ensino. O Campus Paranavaí oferece cursos técnicos integrados ao ensino
médio e cursos superiores, atendendo estudantes, professores e
comunidade da cidade de Paranavaí e região noroeste do Paraná.

## Instrução

Sua única responsabilidade é decidir como processar a mensagem do usuário:
- Se for saudação, agradecimento ou mensagem sem pergunta acadêmica: responda diretamente.
- Se for qualquer dúvida sobre o IFPR Paranavaí: chame obrigatoriamente a tool `buscar_documentos`.

Antes de decidir, raciocine internamente:
1. A mensagem contém uma pergunta ou dúvida acadêmica?
2. Se sim, quais termos vagos precisam ser expandidos?
3. O histórico tem contexto necessário para tornar a pergunta autossuficiente?

## Detalhes

Ao chamar `buscar_documentos`, siga estas regras:

`query` — máximo 10 palavras, curta e objetiva:
- Expanda APENAS termos vagos presentes na mensagem do usuário:
  - "grade" ou "matérias" → "matriz curricular componentes curriculares"
  - "regras" → "regulamento normativa resolução"
  - "vagas" → "vagas ofertadas processo seletivo"
  - "cotas" → "ações afirmativas sistema de cotas"
  - "faltas" → "frequência mínima regime de faltas"
  - "aprovação" → "critérios de aprovação média mínima"
- Não adicione termos que o usuário não mencionou.

`user_question` — pergunta completa e autossuficiente:
- Reformule incorporando contexto do histórico se necessário.
- O replier não terá acesso ao histórico — a pergunta deve fazer sentido sozinha.
- Não utilize os termos "IFPR" e "Campus", use apenas "Paranavaí"

"""

class BuscarDocumentos(BaseModel):
    model_config = ConfigDict(title="buscar_documentos")

    query: str = Field(
        description=(
            "Query otimizada para busca vetorial entre diversos documentos do IFPR Campus Paranavaí. Máximo 10 palavras. "
            "Expandir termos vagos com vocabulario institucional do IFPR."
        ),
    )

    user_question: str = Field(
        description=(
            "Pergunta reformulada de forma autossuficiente para o replier, "
            "incorporando contexto do historico se necessario."
        ),
    )


@dataclass(frozen=True)
class RouteOrRetrieveMessageResult:
    direct_response: str | None
    query: str | None
    user_question: str
    documents: list[Document]


class RouteOrRetrieveMessageUseCase:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        top_k: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._top_k = top_k
        self._chat_model: ChatOpenAI | None = None

    @property
    def is_configured(self) -> bool:
        return self._api_key is not None

    def warm_up(self) -> None:
        self._get_chat_model()
        build_qdrant_retriever(self._top_k)

    async def execute(self, messages: list[ChatMessage]) -> RouteOrRetrieveMessageResult:
        sanitized_messages = [
            message.model_copy(update={"content": message.content.strip()})
            for message in messages
            if message.content.strip()
        ]

        if not sanitized_messages:
            raise ValueError("Nenhuma mensagem valida foi enviada.")

        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

        response = await self._get_chat_model().ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=self._format_messages(sanitized_messages)),
            ],
        )
        tool_call = self._find_buscar_documentos_call(response)

        if not tool_call:
            direct_response = self._extract_text_content(response.content).strip()

            if not direct_response:
                direct_response = "Ola! Como posso ajudar sobre o IF?"

            return RouteOrRetrieveMessageResult(
                direct_response=direct_response,
                query=None,
                user_question=sanitized_messages[-1].content,
                documents=[],
            )

        tool_args = tool_call.get("args") or {}
        query = str(tool_args.get("query") or "").strip()
        user_question = str(tool_args.get("user_question") or "").strip()

        if not query or not user_question:
            raise ValueError(
                "A tool buscar_documentos deve informar query e user_question.",
            )

        print(f"[IFormante][RouterTool] query={query}", flush=True)
        logger.info(
            "chat.router_tool query=%r user_question=%r history_count=%s top_k=%s",
            query,
            user_question,
            len(sanitized_messages),
            self._top_k,
        )
        documents = await self._retrieve_context(query)

        return RouteOrRetrieveMessageResult(
            direct_response=None,
            query=query,
            user_question=user_question,
            documents=documents,
        )

    def _get_chat_model(self) -> ChatOpenAI:
        if self._chat_model is None:
            self._chat_model = ChatOpenAI(
                api_key=self._api_key,
                model=self._model,
                temperature=0,
            ).bind_tools([BuscarDocumentos])

        return self._chat_model

    async def _retrieve_context(self, query: str) -> list[Document]:
        documents = await build_qdrant_retriever(self._top_k).ainvoke(query)
        logger.info(
            "chat.retrieved_documents count=%s query=%r",
            len(documents),
            query,
        )
        return documents

    def _format_messages(self, messages: list[ChatMessage]) -> str:
        return "\n".join(
            f"{message.role}: {message.content}"
            for message in messages
        )

    def _find_buscar_documentos_call(self, response: Any) -> dict[str, Any] | None:
        tool_calls = getattr(response, "tool_calls", None) or []

        for tool_call in tool_calls:
            if tool_call.get("name") == "BuscarDocumentos":
                return tool_call

            if tool_call.get("name") == "buscar_documentos":
                return tool_call

        return None

    def _extract_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content

        if not isinstance(content, list):
            return ""

        text_parts: list[str] = []

        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])

        return "".join(text_parts)
