from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import create_retriever_tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from app.db import build_qdrant_retriever
from model.chat import ChatMessage


class ChatDomain:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        top_k: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._top_k = top_k
        self._agent_name = "agentic_rag"
        self._agent = None

    @property
    def is_configured(self) -> bool:
        return self._api_key is not None

    def warm_up(self) -> None:
        self._get_agent()

    async def stream_response(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        sanitized_messages = [
            message.model_copy(update={"content": message.content.strip()})
            for message in messages
            if message.content.strip()
        ]

        if not sanitized_messages:
            raise ValueError("Nenhuma mensagem valida foi enviada.")

        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")

        agent = self._get_agent()

        async for message_chunk, metadata in agent.astream(
            {"messages": self._to_langchain_messages(sanitized_messages)},
            stream_mode="messages",
        ):
            if metadata.get("langgraph_node") == "tools":
                continue

            content = self._extract_text_content(message_chunk.content)
            if content:
                yield content

    def _get_agent(self):
        if self._agent is None:
            self._agent = self._build_agent()

        return self._agent

    def _build_agent(self):
        SYSTEM_PROMPT = """
            Você é o IFormante, assistente acadêmico do curso de Engenharia de Software do IFPR Campus Paranavaí.

            ## IDENTIDADE
            Não se apresente espontaneamente. Se perguntado o que você é, responda em uma frase.

            ## REGRAS DE ESCOPO — OBRIGATÓRIAS
            Você SOMENTE responde perguntas relacionadas a:
            - Disciplinas, conteúdos e ementas do curso de Engenharia de Software do IFPR Paranavaí
            - Conceitos técnicos de Engenharia de Software (metodologias, padrões, boas práticas, ferramentas)
            - Informações institucionais do IFPR Paranavaí (horários, normas, calendário, etc.)

            Para QUALQUER pergunta fora desse escopo — incluindo outros cursos, outros campi, assuntos gerais, opiniões, 
            cotidiano, outras áreas do conhecimento — responda EXATAMENTE:
            "Não posso ajudar com isso. Sou especializado no curso de Engenharia de Software do IFPR Paranavaí."
            Não elabore. Não justifique. Não sugira alternativas.

            ## REGRAS DE RESPOSTA
            - Saudações e mensagens sem conteúdo ("oi", "olá", "tudo bem"): responda com no máximo 10 tokens.
            - Demais respostas: seja direto e conciso. Sem introduções, sem repetições.
            - Use linguagem técnica quando pertinente, sem ser pedante.

            ## FORMATAÇÃO
            - Dados estruturados (comparações, listas de disciplinas, requisitos, notas): use tabelas Markdown.
            - Conceitos únicos ou explicações: use prosa ou listas simples.

            ## FONTE DE INFORMAÇÃO — CRÍTICO
            Você NÃO possui conhecimento próprio sobre o IFPR Paranavaí nem sobre o curso.
            Para toda pergunta dentro do escopo, você DEVE obrigatoriamente chamar a ferramenta `buscar_documentos` antes de responder.
            NUNCA responda com base em conhecimento externo ou treinamento prévio.
            Se a ferramenta não retornar informação suficiente, diga: "Não encontrei essa informação na base de dados."
        """

        model = ChatOpenAI(
            api_key=self._api_key,
            model=self._model,
            temperature=0.2,
            streaming=True,
        )

        retriever_tool = create_retriever_tool(
            build_qdrant_retriever(self._top_k),
            name="buscar_documentos",
            description=(
                "OBRIGATÓRIO para toda pergunta sobre o curso de Engenharia de Software do IFPR Paranavaí. "
                "Use para buscar disciplinas, ementas, normas, calendário, conteúdos e informações institucionais. "
                "Sempre chame esta ferramenta antes de formular qualquer resposta sobre o curso ou o campus."
            ),
        )

        return create_agent(
            model=model,
            tools=[retriever_tool],
            system_prompt=SYSTEM_PROMPT,
            name=self._agent_name,
        )

    def _to_langchain_messages(self, messages: list[ChatMessage]) -> list[BaseMessage]:
        converted_messages: list[BaseMessage] = []

        for message in messages:
            if message.role == "assistant":
                converted_messages.append(AIMessage(content=message.content))
            else:
                converted_messages.append(HumanMessage(content=message.content))

        return converted_messages

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
