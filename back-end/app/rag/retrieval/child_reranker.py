import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


SYSTEM_PROMPT = """Você é um reranker de trechos para um sistema RAG.

Ordene todos os trechos recebidos do mais relevante ao menos relevante para
responder à pergunta. Considere cobertura factual, relação direta com a pergunta
e presença de detalhes necessários para uma resposta completa.

Retorne somente um array JSON com todos os pseudo-IDs, na ordem escolhida.
Não retorne objeto, explicação, Markdown ou texto adicional.

- Se houver menção a outros campos, lembre-se que você representa apenas o Campus IFPR Paranavaí

Exemplo: ["child_3", "child_1", "child_2"]
"""


@dataclass(frozen=True)
class RerankCandidate:
    pseudo_id: str
    content: str


class ChildReranker:
    def __init__(self, api_key: str, model: str = "gpt-5-nano") -> None:
        model_options: dict[str, Any] = {}
        if model.startswith("gpt-5"):
            model_options["reasoning_effort"] = "minimal"
        self._model = ChatOpenAI(
            api_key=api_key,
            model=model,
            **model_options,
        )

    async def rerank(
        self,
        query: str,
        candidates: list[RerankCandidate],
    ) -> list[str]:
        if not candidates:
            return []
        started_at = perf_counter()
        try:
            content = "\n\n".join(
                f"[{candidate.pseudo_id}]\n{candidate.content}"
                for candidate in candidates
            )
            response = await self._model.ainvoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(
                        content=f"PERGUNTA:\n{query}\n\nTRECHOS:\n{content}",
                    ),
                ],
            )
            return self._validate_order(
                self._parse_array(self._text(response.content)),
                [candidate.pseudo_id for candidate in candidates],
            )
        finally:
            elapsed_ms = (perf_counter() - started_at) * 1000
            print(
                "[RAG] Reranker "
                f"children={len(candidates)} "
                f"elapsed_ms={elapsed_ms:.2f}",
                flush=True,
            )

    def _parse_array(self, raw: str) -> list[str]:
        try:
            parsed = json.loads(raw.strip())
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, str)]

    def _validate_order(
        self,
        proposed: list[str],
        expected: list[str],
    ) -> list[str]:
        expected_set = set(expected)
        ordered: list[str] = []
        seen: set[str] = set()
        for pseudo_id in proposed:
            if pseudo_id in expected_set and pseudo_id not in seen:
                ordered.append(pseudo_id)
                seen.add(pseudo_id)
        ordered.extend(pseudo_id for pseudo_id in expected if pseudo_id not in seen)
        return ordered

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
