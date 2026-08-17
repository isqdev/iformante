import asyncio

from sqlalchemy import text

from app.db.postgres import async_session
from app.repositories import RagRepository


async def main() -> None:
    if async_session is None:
        raise RuntimeError("DATABASE_URL nao configurada.")

    embedding = [0.001] * 1536
    async with async_session() as session:
        candidates = await RagRepository(session).search_child_candidates(
            embedding=embedding,
            limit=32,
        )
        print(
            {
                "children": len(candidates),
                "first_child": candidates[0] if candidates else None,
            },
        )

        await session.execute(text("SET LOCAL enable_seqscan = off"))
        plan = await session.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT id, parent_id, content,
                       1.0 - (embedding <=> CAST(:embedding AS vector))
                           AS vector_score
                FROM rag_document_children
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT 32
                """,
            ),
            {"embedding": str(embedding)},
        )
        print("\n".join(row[0] for row in plan))


if __name__ == "__main__":
    asyncio.run(main())
