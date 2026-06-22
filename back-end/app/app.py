import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI

from app.config import settings
from app.factories.chat import (
    get_reply_message_use_case,
    get_route_or_retrieve_message_use_case,
)
from app.routes import chat_router, conversation_router, document_router, test_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.openai_api_key and settings.qdrant_url:
        started_at = perf_counter()
        get_route_or_retrieve_message_use_case().warm_up()
        get_reply_message_use_case().warm_up()
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
app.include_router(test_router)

@app.get("/")
async def root():
    return {"message": "IFormante API ready"}
