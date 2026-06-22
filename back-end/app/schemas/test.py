from pydantic import BaseModel, Field


class TestSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=8, ge=1, le=50)

    def sanitized_query(self) -> str:
        return self.query.strip()


class TestChunkResult(BaseModel):
    document_id: str
    chunk_id: str | None = None
    parent_id: str | None = None
    score: float | None = None
    title: str | None = None
    source_url: str | None = None
    type: str | None = None
    page: int | None = None
    page_numbers: list[int] = []
    section_path: list[str] = []
    text: str
    bounding_boxes: list[dict[str, float | int]] = []


class TestSearchResponse(BaseModel):
    query: str
    raw_results: list[TestChunkResult]
    mmr_results: list[TestChunkResult]
    reranked_results: list[TestChunkResult]
