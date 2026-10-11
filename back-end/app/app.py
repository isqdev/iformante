import logging
import asyncio
from contextlib import suppress
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
import os
from urllib.parse import urlsplit
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from app.routes.auth import router as auth_router
from app.routes.call import router as call_router, piper_service
from app.security.auth import AuthError
from app.services.auth_mail import mail_worker, smtp_ready
from app.db.postgres import async_session

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

    worker = asyncio.create_task(mail_worker(async_session)) if smtp_ready() and async_session else None
    voice_worker = asyncio.create_task(piper_service.warm_up()) if piper_service.configured else None
    if voice_worker:
        def log_voice_result(task):
            if not task.cancelled() and task.exception():
                logger.error("call.voice_warmup_failed: %s", task.exception())
        voice_worker.add_done_callback(log_voice_result)
    yield
    if voice_worker and not voice_worker.done():
        voice_worker.cancel()
        with suppress(asyncio.CancelledError):
            await voice_worker
    await piper_service.close()
    if worker:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(title="IFormante API", lifespan=lifespan)

@app.middleware("http")
async def check_origin(request, call_next):
    origin = request.headers.get("origin")
    allowed = os.getenv("APP_PUBLIC_URL", "http://localhost:3000").rstrip("/")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin.rstrip("/") != allowed:
        return JSONResponse({"detail": "Origem inválida."}, status_code=403)
    return await call_next(request)


app.include_router(chat_router)
app.include_router(conversation_router)
app.include_router(document_router)
app.include_router(auth_router)
app.include_router(call_router)


@app.exception_handler(AuthError)
async def auth_error_handler(request, error):
    return JSONResponse({"detail": str(error)}, status_code=error.status)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, error):
    # Never echo request bodies containing e-mails, passwords or reset tokens.
    return JSONResponse({"detail": "Confira os campos informados.", "fields": [list(item["loc"])[1:] for item in error.errors()]}, status_code=422)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request, error):
    return JSONResponse({"detail": "Este cadastro ou documento já existe."}, status_code=409)

@app.get("/")
async def root():
    return {"message": "IFormante API ready"}
