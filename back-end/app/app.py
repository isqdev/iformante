import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI

from app.config import settings
from app.routes import chat_router, conversation_router, document_router
from app.routes.chat import get_chat_domain

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.openai_api_key and settings.qdrant_url:
        started_at = perf_counter()
        get_chat_domain().warm_up()
        logger.info(
            "chat.warmup_elapsed_ms=%s",
            round((perf_counter() - started_at) * 1000),
        )
    else:
        logger.info("chat.warmup_skipped=missing_openai_or_qdrant_config")

    yield


app = FastAPI(title="IFormante API", lifespan=lifespan)

app.include_router(chat_router)
app.include_router(conversation_router)
app.include_router(document_router)

@app.get("/")
async def root():
    return {"message": "IFormante API ready"}
