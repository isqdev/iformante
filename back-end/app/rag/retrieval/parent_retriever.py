from dataclasses import dataclass
from time import perf_counter

from langchain_openai import OpenAIEmbeddings

from app.models import RagDocumentParent
from app.repositories import RagRepository

from .child_reranker import ChildReranker, RerankCandidate


@dataclass(frozen=True)
class RetrievedParent:
    id: str
    document_id: str
    content: str
    bbox: list[dict] | None
    source_url: str | None
    filename: str
    source_type: str = "PDF"


@dataclass(frozen=True)
class RetrievedChildCandidate:
    child_id: str
    parent_id: str
    vector_rank: int
    vector_score: float
    rerank_rank: int


@dataclass(frozen=True)
class ParentRetrievalResult:
    parents: list[RetrievedParent]
    children: list[RetrievedChildCandidate]
    best_child_by_parent: dict[str, str]


class ParentRetriever:
    def __init__(
        self,
        api_key: str | None,
        embedding_model: str,
        top_k: int,
        repository: RagRepository,
        reranker_model: str = "gpt-5-nano",
        candidate_count: int = 32,
    ) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no back-end.")
        if candidate_count < top_k:
            raise ValueError(
                "RAG_CANDIDATE_COUNT deve ser maior ou igual a RAG_TOP_K.",
            )
        self._embeddings = OpenAIEmbeddings(
            api_key=api_key,
            model=embedding_model,
        )
        self._top_k = top_k
        self._repository = repository
        self._reranker = ChildReranker(api_key, reranker_model)
        self._candidate_count = candidate_count

    async def retrieve(self, query: str) -> ParentRetrievalResult:
        embedding_started_at = perf_counter()
        embedding = await self._embeddings.aembed_query(query)
        self._print_timing("embedding", embedding_started_at)

        vector_started_at = perf_counter()
        vector_candidates = await self._repository.search_child_candidates(
            embedding,
            self._candidate_count,
        )
        self._print_timing("vector_search", vector_started_at)
        pseudo_id_to_child = {
            f"child_{index}": child
            for index, child in enumerate(vector_candidates, start=1)
        }
        reranked_pseudo_ids = await self._reranker.rerank(
            query,
            [
                RerankCandidate(pseudo_id, child.content)
                for pseudo_id, child in pseudo_id_to_child.items()
            ],
        )
        reranked_children = [
            pseudo_id_to_child[pseudo_id]
            for pseudo_id in reranked_pseudo_ids
            if pseudo_id in pseudo_id_to_child
        ]

        parent_ids: list[str] = []
        best_child_by_parent: dict[str, str] = {}
        for child in reranked_children:
            if child.parent_id in best_child_by_parent:
                continue
            best_child_by_parent[child.parent_id] = child.child_id
            parent_ids.append(child.parent_id)
            if len(parent_ids) == self._top_k:
                break

        parent_fetch_started_at = perf_counter()
        parents = await self._repository.get_parents_by_ids(parent_ids)
        self._print_timing("parent_fetch", parent_fetch_started_at)
        rerank_rank_by_child = {
            child.child_id: rank
            for rank, child in enumerate(reranked_children, start=1)
        }
        return ParentRetrievalResult(
            parents=[self._to_result(parent) for parent in parents],
            children=[
                RetrievedChildCandidate(
                    child_id=child.child_id,
                    parent_id=child.parent_id,
                    vector_rank=child.vector_rank,
                    vector_score=child.vector_score,
                    rerank_rank=rerank_rank_by_child[child.child_id],
                )
                for child in reranked_children
            ],
            best_child_by_parent=best_child_by_parent,
        )

    def _print_timing(self, stage: str, started_at: float) -> None:
        elapsed_ms = (perf_counter() - started_at) * 1000
        print(f"[RAG] {stage}_elapsed_ms={elapsed_ms:.2f}", flush=True)

    def _to_result(self, parent: RagDocumentParent) -> RetrievedParent:
        from app.services.pdf_anchors import chunk_anchors
        anchors = parent.bbox or []
        if parent.document.source_type == "PDF" and anchors and not any("x" in a for a in anchors):
            anchors = chunk_anchors(parent.document.stored_path, int(anchors[0].get("page", 1)), parent.content)
        return RetrievedParent(
            id=parent.id,
            document_id=parent.document_id,
            content=parent.content,
            bbox=anchors,
            source_url=parent.document.source_url,
            filename=parent.document.file_name or parent.document.title,
            source_type=parent.document.source_type,
        )
