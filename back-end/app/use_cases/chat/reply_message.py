from collections.abc import AsyncIterator
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

SYSTEM_PROMPT = """
Você é um assistente acadêmico do IFPR Campus Paranavaí.

Sua missão é tirar dúvidas de estudantes, professores e funcionários do IFPR
Paranavaí usando exclusivamente informações contidas em documentos institucionais.

## Escopo geográfico

Você representa EXCLUSIVAMENTE o Campus Paranavaí.
Mesmo que o contexto contenha informações de outros campi do IFPR, ignore-as
completamente.
Considere apenas trechos que se refiram explicitamente a Paranavaí ou normas gerais
aplicáveis a todos os campi sem distinção de localidade.
Se a pergunta for sobre outro campus, responda exatamente: "Não posso ajudar com isso."

## Regras de resposta

- Use exclusivamente o contexto fornecido. Não use conhecimento externo.
- Suas respostas devem ser sempre completas, incluindo TODOS os dados pertinentes
  presentes no contexto
— Sempre inclua informações relevantes para a pergunta.
- Se o contexto não for suficiente, diga que não encontrou essa informação nos
  documentos disponíveis.
- Se responder com dados estruturados, use tabela Markdown.
- Não mencione fontes, documentos, URLs ou páginas na resposta.
- Se a pergunta estiver fora do escopo, responda exatamente: "Não posso ajudar com isso."
"""


class ReplyMessageUseCase:
    def __init__(self, api_key: str | None, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._chat_model: ChatOpenAI | None = None

    @property
    def is_configured(self) -> bool:
        return self._api_key is not None

    def warm_up(self) -> None:
        self._get_chat_model()

    async def stream(
        self,
        user_question: str,
        documents: list[Document],
    ) -> AsyncIterator[str]:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

        if not documents:
            yield "Nao encontrei essa informacao nos documentos disponiveis."
            return

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    "CONTEXTO:\n\n"
                    f"{self._format_context_documents(documents)}\n\n"
                    "PERGUNTA:\n\n"
                    f"{user_question}"
                ),
            ),
        ]

        async for message_chunk in self._get_chat_model().astream(messages):
            content = self._extract_text_content(message_chunk.content)

            if content:
                yield content

    def _get_chat_model(self) -> ChatOpenAI:
        if self._chat_model is None:
            self._chat_model = ChatOpenAI(
                api_key=self._api_key,
                model=self._model,
                temperature=0.2,
                streaming=True,
            )

        return self._chat_model

    def _format_context_documents(self, documents: list[Document]) -> str:
        formatted_documents: list[str] = []

        for index, document in enumerate(documents, start=1):
            metadata = document.metadata
            page_numbers = metadata.get("page_numbers") or [metadata.get("page")]
            page_numbers = [page for page in page_numbers if page is not None]
            pages = ", ".join(str(page) for page in page_numbers) or "nao identificada"
            formatted_documents.append(
                "\n".join(
                    [
                        f"[Trecho {index}]",
                        f"Documento: {metadata.get('title') or metadata.get('filename') or 'desconhecido'}",
                        f"URL: {metadata.get('source_url') or 'desconhecida'}",
                        f"Paginas: {pages}",
                        f"Tipo: {metadata.get('type') or 'desconhecido'}",
                        f"Secao: {' > '.join(metadata.get('section_path') or []) or 'nao identificada'}",
                        "Conteudo:",
                        document.page_content,
                    ],
                ),
            )

        return "\n\n".join(formatted_documents)

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
