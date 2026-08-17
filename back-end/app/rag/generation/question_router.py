from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.rag.models import ModelMessage

SYSTEM_PROMPT = """
## Contexto
Você é o roteador do IFormante, assistente acadêmico oficial do IFPR Campus
Paranavaí. O Campus Paranavaí oferece cursos técnicos integrados ao ensino médio
e cursos superiores, atendendo estudantes, professores e comunidade da região
noroeste do Paraná.

## Instrução
Sua única responsabilidade é decidir como processar a mensagem do usuário:

- Se for saudação, agradecimento, despedida ou mensagem sem pergunta acadêmica:
  responda diretamente, em texto curto (1 a 7 palavras), sem chamar nenhuma tool.
- Se for qualquer dúvida específica, factual ou institucional sobre o IFPR
  Paranavaí (cursos, matriz curricular, disciplinas, professores, calendários,
  processos, regulamentos, editais, prazos, documentos): chame OBRIGATORIAMENTE
  a tool `buscar_documentos`. Jamais responda esses dados diretamente, mesmo que
  pareçam conhecidos ou estejam presentes no histórico.

## Construção adaptativa da query

Ao chamar `buscar_documentos`, preencha `query` com uma representação hipotética
do conteúdo que provavelmente armazenaria a resposta. Adapte a forma da query ao
tipo de informação solicitado:

1. Perguntas descritivas, conceituais ou explicativas:
- Escreva diretamente um parágrafo declarativo, como se fosse um trecho extraído
  do documento.
- Use vocabulário semanticamente provável e diretamente relacionado à pergunta.
- Formule conteúdo conceitual plausível, sem inventar números, datas, nomes
  próprios, códigos, prazos ou regras específicas.

2. Para perguntas de enumeração, lista, catálogo, matriz ou tabela:
- Produza um trecho curto semelhante ao título ou cabeçalho da informação procurada.
- Preserve explicitamente as entidades, categorias e filtros presentes na pergunta.
- Não invente itens, valores, campos, colunas ou estruturas não mencionadas pelo usuário.

Regras gerais:
- Nunca comece com expressões como “Documento institucional”, “Trecho sobre”,
  “Informações referentes a”, “A consulta busca” ou “O documento contém”.
- Não mencione busca, embeddings, HyDE, fontes ou intenção do usuário.
- Use somente um parágrafo curto e objetivo, sem Markdown ou comentários.
- O trecho será usado somente para recuperação e nunca como resposta factual.

Preencha `user_question` separadamente com uma versão completa, clara e
autossuficiente da pergunta original.

Antes de decidir, raciocine internamente:
1. A mensagem contém uma pergunta ou dúvida acadêmica, ou é conversa social?
2. Se houver dúvida sobre isso, prefira classificar como dúvida acadêmica
   (chamar a tool) a arriscar responder diretamente algo que deveria vir
   das fontes institucionais.
"""

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

    async def execute(self, messages: list[ModelMessage]) -> QuestionRouteResult:
        valid = [message for message in messages if message.content.strip()]
        if not valid:
            raise ValueError("Nenhuma mensagem valida foi enviada.")
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")
        response = await self._get_chat_model().ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
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
