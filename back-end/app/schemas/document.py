from pydantic import BaseModel, Field


class DownloadDocumentRequest(BaseModel):
    url: str = Field(min_length=1)


class DownloadDocumentResponse(BaseModel):
    filename: str
    path: str
    chunks_indexed: int


class DocumentResponse(BaseModel):
    id: str
    name: str
    url: str


class DeleteDocumentResponse(BaseModel):
    document_id: str
    deleted: bool
