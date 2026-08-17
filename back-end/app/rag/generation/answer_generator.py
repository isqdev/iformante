import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.rag.retrieval import RetrievedParent


SYSTEM_PROMPT = """Você é um assistente acadêmico do IFPR Campus Paranavaí.

Sua missão é tirar dúvidas de estudantes, professores e funcionários do IFPR
Paranavaí usando exclusivamente informações contidas nas fontes fornecidas,
identificadas por [parent_N].

## Escopo geográfico

Você representa EXCLUSIVAMENTE o Campus Paranavaí.
Mesmo que as fontes contenham informações de outros campi do IFPR, ignore-as
completamente.
Se houver menção a outros campus, considere apenas trechos que se refiram explicitamente a Paranavaí ou normas gerais
aplicáveis a todos os campi sem distinção de localidade.
Se a pergunta for sobre outro campus, responda exatamente: "Não posso ajudar com isso."

## Regras de resposta

- Use exclusivamente as fontes fornecidas. Não use conhecimento externo.
- Suas respostas devem ser sempre completas, incluindo TODOS os dados pertinentes
  presentes nas fontes.
- Sempre inclua informações relevantes para a pergunta, mesmo que não tenham sido
  explicitamente solicitadas, desde que ajudem a esclarecer o contexto da resposta.
- Quando a pergunta envolver um valor que seja resultado de uma soma, total ou
  subtotal presente em uma tabela ou estrutura hierárquica (ex: carga horária total
  composta por obrigatórias, optativas, estágio, atividades complementares, extensão),
  não responda apenas com o valor final — apresente também a composição/breakdown
  completo que forma esse valor, para que o usuário entenda de onde ele vem.
- Se as fontes forem parciais, declare claramente a limitação.
- Não invente informações para preencher lacunas.
- Se responder com dados estruturados, use tabela Markdown.
- Não mencione fontes, documentos, URLs ou páginas no texto da resposta.
- Se a pergunta estiver fora do escopo, responda exatamente: "Não posso ajudar com isso."
- Priorize tabelas para dados estruturados.
- Utilize Headers markdown (#) para organizar as respostas para facilitar a leitura.
- Toda sentença deve começar com letra maiúscula.
- Não comece a resposta com um header.

## Formato de saída

Ao final da resposta, retorne um bloco JSON delimitado por ```json e ``` contendo
APENAS os labels das fontes que de fato utilizou:
{"used_sources": ["parent_1"]}
Se nenhuma fonte foi suficiente, use {"used_sources": []} e informe isso no texto.
"""


@dataclass(frozen=True)
class AnswerResult:
    content: str
    used_parent_ids: list[str]


@dataclass(frozen=True)
class AnswerDelta:
    content: str


class AnswerGenerator:
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
        question: str,
        parents: list[RetrievedParent],
    ) -> AsyncIterator[AnswerDelta | AnswerResult]:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

        labels = {
            f"parent_{index}": parent.id
            for index, parent in enumerate(parents, start=1)
        }
        context = "\n\n".join(
            f"[{label}]\n{parent.content}"
            for label, parent in zip(labels, parents, strict=True)
        )
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"FONTES:\n{context}\n\nPERGUNTA:\n{question}"),
        ]
        marker = "```json"
        raw_parts: list[str] = []
        pending = ""
        parsing_sources = False

        async for chunk in self._get_chat_model().astream(messages):
            text = self._text(chunk.content)
            if not text:
                continue
            raw_parts.append(text)
            if parsing_sources:
                continue
            pending += text
            marker_index = pending.find(marker)
            if marker_index >= 0:
                visible = pending[:marker_index]
                if visible:
                    yield AnswerDelta(visible)
                parsing_sources = True
                pending = ""
                continue
            safe_length = len(pending) - len(marker) + 1
            if safe_length > 0:
                yield AnswerDelta(pending[:safe_length])
                pending = pending[safe_length:]

        raw = "".join(raw_parts)
        if not parsing_sources and pending:
            yield AnswerDelta(pending)
        content, labels_used = self._extract_sources(raw)
        yield AnswerResult(
            content=content,
            used_parent_ids=[
                labels[label] for label in labels_used if label in labels
            ],
        )

    async def answer(
        self,
        question: str,
        parents: list[RetrievedParent],
    ) -> AnswerResult:
        result: AnswerResult | None = None
        async for event in self.stream(question, parents):
            if isinstance(event, AnswerResult):
                result = event
        if result is None:
            raise RuntimeError("A IA nao finalizou a resposta.")
        return result

    def _get_chat_model(self) -> ChatOpenAI:
        if self._chat_model is None:
            self._chat_model = ChatOpenAI(
                api_key=self._api_key,
                model=self._model,
                temperature=0,
            )
        return self._chat_model

    def _extract_sources(self, raw: str) -> tuple[str, list[str]]:
        start = raw.rfind("```json")
        if start < 0:
            return raw.strip(), []
        end = raw.find("```", start + len("```json"))
        if end < 0:
            return raw.strip(), []
        try:
            payload = json.loads(raw[start + len("```json"):end].strip())
        except json.JSONDecodeError:
            return raw[:start].strip(), []
        labels = payload.get("used_sources", [])
        if not isinstance(labels, list) or not all(
            isinstance(label, str) for label in labels
        ):
            labels = []
        return (raw[:start] + raw[end + 3:]).strip(), labels

    def _text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
            )
        return ""
