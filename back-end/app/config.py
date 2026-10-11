from dataclasses import dataclass
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None

    openai_model: str

    openai_embedding_model: str

    openai_embedding_dimensions: int

    rag_top_k: int

    rag_candidate_count: int

    rag_reranker_model: str

    database_url: str | None

    document_storage_dir: str

    document_remote_base_url: str | None = None
    groq_api_key: str | None = None
    piper_model_path: str = "voices/pt_BR-faber-medium.onnx"

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            openai_embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL",
                "text-embedding-3-small",
            ),
            openai_embedding_dimensions=int(
                os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536"),
            ),
            rag_top_k=int(os.getenv("RAG_TOP_K", "8")),
            rag_candidate_count=int(
                os.getenv("RAG_CANDIDATE_COUNT", "32"),
            ),
            rag_reranker_model=os.getenv(
                "RAG_RERANKER_MODEL",
                "gpt-5-nano",
            ),
            database_url=Settings._normalize_database_url(os.getenv("DATABASE_URL")),
            document_storage_dir=os.getenv("DOCUMENT_STORAGE_DIR", "downloads"),
            document_remote_base_url=os.getenv("DOCUMENT_REMOTE_BASE_URL") or None,
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            piper_model_path=os.getenv("PIPER_MODEL_PATH", "voices/pt_BR-faber-medium.onnx"),
        )

    @staticmethod
    def _normalize_database_url(database_url: str | None) -> str | None:
        if not database_url:
            return None

        normalized_url = database_url

        if normalized_url.startswith("postgresql://"):
            normalized_url = normalized_url.replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )
        elif normalized_url.startswith("postgres://"):
            normalized_url = normalized_url.replace(
                "postgres://",
                "postgresql+asyncpg://",
                1,
            )

        parsed_url = urlsplit(normalized_url)
        query_params = dict(parse_qsl(parsed_url.query, keep_blank_values=True))

        if "sslmode" in query_params and "ssl" not in query_params:
            query_params["ssl"] = query_params["sslmode"]

        query_params.pop("sslmode", None)
        query_params.pop("channel_binding", None)

        return urlunsplit(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                urlencode(query_params),
                parsed_url.fragment,
            ),
        )


settings = Settings.from_env()
