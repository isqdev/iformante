from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RagRetrievalAudit


class RagRetrievalAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, audit: RagRetrievalAudit) -> RagRetrievalAudit:
        self._session.add(audit)
        await self._session.flush()
        return audit
