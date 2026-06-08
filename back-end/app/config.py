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
    qdrant_url: str | None
    qdrant_api_key: str | None
    qdrant_collection: str
    rag_top_k: int
    database_url: str | None

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
            qdrant_url=os.getenv("QDRANT_URL"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            qdrant_collection=os.getenv("QDRANT_COLLECTION", "my-collection"),
            rag_top_k=int(os.getenv("RAG_TOP_K", "4")),
            database_url=Settings._normalize_database_url(os.getenv("DATABASE_URL")),
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
