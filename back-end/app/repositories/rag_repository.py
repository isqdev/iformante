from dataclasses import dataclass

from sqlalchemy import case, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import RagDocumentChild, RagDocumentParent


@dataclass(frozen=True)
class VectorChildCandidate:
    child_id: str
    parent_id: str
    content: str
    vector_rank: int
    vector_score: float


class RagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_document_chunks(
        self,
        document_id: str,
        parents: list[RagDocumentParent],
        children: list[RagDocumentChild],
    ) -> None:
        existing = await self._session.execute(
            select(RagDocumentParent).where(
                RagDocumentParent.document_id == document_id,
            ),
        )
        for parent in existing.scalars():
            await self._session.delete(parent)
        self._session.add_all(parents)
        self._session.add_all(children)
        await self._session.flush()

    async def search_child_candidates(
        self,
        embedding: list[float],
        limit: int = 32,
    ) -> list[VectorChildCandidate]:
        result = await self._session.execute(
            self._build_child_candidates_statement(embedding, limit),
        )
        return [
            VectorChildCandidate(
                child_id=row["child_id"],
                parent_id=row["parent_id"],
                content=row["content"],
                vector_rank=rank,
                vector_score=float(row["vector_score"]),
            )
            for rank, row in enumerate(result.mappings().all(), start=1)
        ]

    async def get_parents_by_ids(
        self,
        parent_ids: list[str],
    ) -> list[RagDocumentParent]:
        if not parent_ids:
            return []
        ordering = case(
            {parent_id: rank for rank, parent_id in enumerate(parent_ids)},
            value=RagDocumentParent.id,
        )
        result = await self._session.execute(
            select(RagDocumentParent)
            .where(RagDocumentParent.id.in_(parent_ids))
            .options(selectinload(RagDocumentParent.document))
            .order_by(ordering),
        )
        return list(result.scalars().all())

    def _build_child_candidates_statement(
        self,
        embedding: list[float],
        limit: int = 32,
    ):
        distance = RagDocumentChild.embedding.cosine_distance(embedding)
        return (
            select(
                RagDocumentChild.id.label("child_id"),
                RagDocumentChild.parent_id.label("parent_id"),
                RagDocumentChild.content,
                (literal(1.0) - distance).label("vector_score"),
            )
            .order_by(distance)
            .limit(limit)
        )
