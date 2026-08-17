import argparse
import asyncio

from sqlalchemy import delete, func, select

from app.db.postgres import async_session
from app.models import (
    Document,
    Message,
    MessageSource,
    RagDocumentChild,
    RagDocumentParent,
)


async def clear() -> None:
    if async_session is None:
        raise RuntimeError("DATABASE_URL nao configurada.")
    tracked_models = (
        Document,
        MessageSource,
        RagDocumentParent,
        RagDocumentChild,
        Message,
    )
    async with async_session() as session:
        before = {
            model.__tablename__: await session.scalar(
                select(func.count()).select_from(model),
            )
            for model in tracked_models
        }
        await session.execute(delete(Document))
        await session.commit()
        after = {
            model.__tablename__: await session.scalar(
                select(func.count()).select_from(model),
            )
            for model in tracked_models
        }
    print({"before": before, "after": after})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirma a exclusao de todos os documentos e dados dependentes.",
    )
    arguments = parser.parse_args()
    if not arguments.confirm:
        parser.error("Use --confirm para executar a limpeza.")
    asyncio.run(clear())
