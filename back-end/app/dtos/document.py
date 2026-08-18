from pydantic import BaseModel, Field


class CreateWebPageRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class IngestDocumentResponse(BaseModel):
    filename: str
    path: str
    chunks_indexed: int


class DocumentResponse(BaseModel):
    id: str
    name: str
    url: str | None
    source_type: str


class DeleteDocumentResponse(BaseModel):
    document_id: str
    deleted: bool
