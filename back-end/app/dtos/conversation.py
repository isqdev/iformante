from pydantic import BaseModel, Field


class CitationResponse(BaseModel):
    chunk_id: str
    anchors: list[dict] = Field(default_factory=list)


class MessageSourceResponse(BaseModel):
    document_id: str
    filename: str
    url: str | None
    source_type: str
    citations: list[CitationResponse] = Field(default_factory=list)


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    response_mode: str = "text"
    playback_status: str | None = None
    sources: list[MessageSourceResponse] = Field(default_factory=list)


class ConversationSummaryResponse(BaseModel):
    id: str
    title: str
    channel: str = "text"


class ConversationResponse(BaseModel):
    id: str
    title: str
    channel: str = "text"
    messages: list[MessageResponse]
