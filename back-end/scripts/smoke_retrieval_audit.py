import asyncio

from sqlalchemy import select

from app.db.postgres import async_session
from app.models import RagRetrievalAudit


async def main() -> None:
    if async_session is None:
        raise RuntimeError("DATABASE_URL nao configurada.")
    async with async_session() as session:
        audit = await session.scalar(
            select(RagRetrievalAudit)
            .order_by(RagRetrievalAudit.created_at.desc())
            .limit(1),
        )
        if audit is None:
            raise RuntimeError("Nenhuma auditoria encontrada.")
        print(
            {
                "message_id": audit.message_id,
                "query": audit.rewritten_query,
                "children": len(audit.retrieved_children),
                "parents": len(audit.retrieved_parents),
                "used_parents": sum(
                    1
                    for parent in audit.retrieved_parents
                    if parent["used"]
                ),
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
