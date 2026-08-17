import asyncio

from sqlalchemy import select

from app.db.postgres import async_session
from app.models import Message, MessageSource
from app.repositories import MessageRepository


async def main() -> None:
    if async_session is None:
        raise RuntimeError("DATABASE_URL nao configurada.")
    async with async_session() as session:
        message_id = await session.scalar(
            select(MessageSource.message_id).order_by(MessageSource.created_at.desc()).limit(1),
        )
        if message_id is None:
            print("Nenhuma fonte persistida encontrada.")
            return
        conversation_id = await session.scalar(
            select(Message.conversation_id).where(Message.id == message_id),
        )
        messages = await MessageRepository(session).list_by_conversation(
            conversation_id,
        )
        message = next(item for item in messages if item.id == message_id)
        print(
            {
                "message_id": message.id,
                "sources": [
                    {
                        "filename": source.document.file_name,
                        "url": source.document.source_url,
                    }
                    for source in message.sources
                ],
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
