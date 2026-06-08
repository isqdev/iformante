from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

if settings.database_url:
    async_engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        async_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
else:
    async_engine = None
    async_session = None


async def get_database_session() -> AsyncIterator[AsyncSession]:
    if async_session is None:
        raise RuntimeError("DATABASE_URL nao configurada no back-end.")

    async with async_session() as session:
        yield session
