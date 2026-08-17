from functools import lru_cache
from app.config import settings
from app.rag.generation import AnswerGenerator, QuestionRouter


@lru_cache(maxsize=1)
def get_question_router() -> QuestionRouter:
    return QuestionRouter(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


@lru_cache(maxsize=1)
def get_answer_generator() -> AnswerGenerator:
    return AnswerGenerator(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )
