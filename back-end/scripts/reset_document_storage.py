import asyncio

from sqlalchemy import delete

from app.config import settings
from app.db.postgres import async_session
from app.db.qdrant import (
    build_qdrant_client,
    ensure_qdrant_collection,
    ensure_qdrant_parent_collection,
    get_parent_collection_name,
)
from app.models import Document


async def reset_document_storage() -> None:
    if async_session is None:
        raise RuntimeError("DATABASE_URL nao configurada no back-end.")

    client = build_qdrant_client()
    child_collection = settings.qdrant_collection
    parent_collection = get_parent_collection_name()

    for collection_name in (child_collection, parent_collection):
        if client.collection_exists(collection_name):
            client.delete_collection(collection_name)
            print(f"Collection removida: {collection_name}", flush=True)

    ensure_qdrant_collection(client, child_collection)
    ensure_qdrant_parent_collection(client, parent_collection)
    print(f"Collection recriada: {child_collection}", flush=True)
    print(f"Collection recriada: {parent_collection}", flush=True)

    async with async_session() as session:
        result = await session.execute(delete(Document))
        await session.commit()

    print(
        f"Documentos removidos do Postgres: {result.rowcount or 0}",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(reset_document_storage())
