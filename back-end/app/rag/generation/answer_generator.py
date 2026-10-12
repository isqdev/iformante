import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.rag.retrieval import RetrievedParent
from app.prompts import DEFAULT_PROMPTS, PROMPT_DEFAULTS
from app.services.speech_text import SPEECH_MAX_WORDS, normalize_speech


SYSTEM_PROMPT = PROMPT_DEFAULTS["prompt_replier"]


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

    async def speech_answer(self, question: str, parents: list[RetrievedParent], *, system_prompt: str | None = None) -> AnswerResult:
        labels = {f"parent_{i}": p.id for i, p in enumerate(parents, 1)}
        context = "\n\n".join(f"[{label}]\n{p.content}" for label, p in zip(labels, parents, strict=True))
        messages = [
            SystemMessage(content=system_prompt if system_prompt is not None else DEFAULT_PROMPTS.voice_prompt(SPEECH_MAX_WORDS)),
            HumanMessage(content=f"FONTES:\n{context}\n\nPERGUNTA:\n{question}"),
        ]
        response = await self._get_chat_model().ainvoke(messages)
        content, used = self._extract_sources(self._text(response.content))
        return AnswerResult(normalize_speech(content), [labels[label] for label in used if label in labels])

    async def prepare_direct_speech(self, text: str, *, system_prompt: str | None = None) -> str:
        spoken = normalize_speech(text)
        if spoken == "Não posso ajudar com isso.":
            return spoken
        response = await self._get_chat_model().ainvoke([
            SystemMessage(content=system_prompt if system_prompt is not None else DEFAULT_PROMPTS.voice_prompt(SPEECH_MAX_WORDS, direct=True)),
            HumanMessage(content=text),
        ])
        return normalize_speech(self._text(response.content))

    async def stream(
        self,
        question: str,
        parents: list[RetrievedParent],
        *, system_prompt: str = SYSTEM_PROMPT,
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
            SystemMessage(content=system_prompt),
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
