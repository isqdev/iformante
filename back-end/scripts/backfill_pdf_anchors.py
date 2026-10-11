"""Rebuild citation coordinates without replacing chunks or generating embeddings."""
import asyncio
from pathlib import Path
from sqlalchemy import select, update, text
from app.db.postgres import async_session, async_engine
from app.models import Document, RagDocumentParent
from app.services.pdf_anchors import chunk_anchors


async def main():
    async with async_session() as session:
        rows = (await session.execute(select(RagDocumentParent, Document).join(
            Document, Document.id == RagDocumentParent.document_id,
        ).where(Document.source_type == "PDF"))).all()
        updates, missing = [], 0
        for parent, document in rows:
            if not document.stored_path or not Path(document.stored_path).is_file():
                missing += 1
                continue
            anchors = parent.bbox or []
            if not anchors:
                missing += 1
                continue
            geometry = await asyncio.to_thread(chunk_anchors, document.stored_path, int(anchors[0].get("page", 1)), parent.content)
            updates.append({"id": parent.id, "bbox": geometry})
        if updates:
            await session.execute(update(RagDocumentParent), updates)
            await session.execute(text("UPDATE message_sources AS source SET bbox = parent.bbox FROM rag_document_parents AS parent WHERE source.chunk_id = parent.id"))
            await session.commit()
        print(f"Chunks atualizados: {len(updates)}; sem arquivo/página disponível: {missing}.")
    await async_engine.dispose()


if __name__ == "__main__": asyncio.run(main())
