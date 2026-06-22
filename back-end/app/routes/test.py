from fastapi import APIRouter, HTTPException, status

from app.db import (
    apply_mmr_to_documents,
    build_hybrid_fusion_query,
    build_qdrant_retriever,
    build_qdrant_vector_store,
)
from app.schemas import TestChunkResult, TestSearchRequest, TestSearchResponse

router = APIRouter(tags=["test"])


def _serialize_chunk_result(
    document_id: str,
    document,
    score: float | None = None,
) -> TestChunkResult:
    metadata = document.metadata

    return TestChunkResult(
        document_id=document_id,
        chunk_id=metadata.get("chunk_id"),
        parent_id=metadata.get("parent_id"),
        score=score,
        title=metadata.get("title"),
        source_url=metadata.get("source_url"),
        type=metadata.get("type"),
        page=metadata.get("page"),
        page_numbers=metadata.get("page_numbers") or [],
        section_path=metadata.get("section_path") or [],
        text=document.page_content,
        bounding_boxes=metadata.get("bounding_boxes") or [],
    )


@router.post("/test", response_model=TestSearchResponse)
async def test_search(payload: TestSearchRequest) -> TestSearchResponse:
    query = payload.sanitized_query()

    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A query nao pode estar vazia.",
        )

    try:
        vector_store = build_qdrant_vector_store()
        candidate_top_k = max(payload.top_k, payload.top_k * 4)
        documents_with_scores = vector_store.similarity_search_with_score(
            query,
            hybrid_fusion=build_hybrid_fusion_query(),
            k=candidate_top_k,
        )
        mmr_documents = apply_mmr_to_documents(
            query=query,
            documents=[document for document, _ in documents_with_scores],
            top_k=payload.top_k,
        )
        reranked_documents = build_qdrant_retriever(payload.top_k).invoke(query)

        raw_results: list[TestChunkResult] = []
        mmr_results: list[TestChunkResult] = []
        reranked_results: list[TestChunkResult] = []

        for document, score in documents_with_scores:
            document_id = str(document.metadata.get("document_id") or "").strip()

            if not document_id:
                continue

            raw_results.append(
                _serialize_chunk_result(document_id, document, score),
            )

        for document in mmr_documents:
            document_id = str(document.metadata.get("document_id") or "").strip()

            if not document_id:
                continue

            mmr_results.append(
                _serialize_chunk_result(document_id, document),
            )

        for document in reranked_documents:
            document_id = str(document.metadata.get("document_id") or "").strip()

            if not document_id:
                continue

            reranked_results.append(
                _serialize_chunk_result(document_id, document),
            )

        return TestSearchResponse(
            query=query,
            raw_results=raw_results,
            mmr_results=mmr_results,
            reranked_results=reranked_results,
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
