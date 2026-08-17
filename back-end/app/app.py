import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI

from app.config import settings
from app.factories.rag import (
    get_answer_generator,
    get_question_router,
)
from app.routes import chat_router, conversation_router, document_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.openai_api_key:
        started_at = perf_counter()
        get_question_router().warm_up()
        get_answer_generator().warm_up()
        logger.info(
            "chat.warmup_elapsed_ms=%s",
            round((perf_counter() - started_at) * 1000),
        )
    else:
        logger.info("chat.warmup_skipped=missing_openai_config")

    yield


app = FastAPI(title="IFormante API", lifespan=lifespan)

app.include_router(chat_router)
app.include_router(conversation_router)
app.include_router(document_router)

@app.get("/")
async def root():
    return {"message": "IFormante API ready"}
