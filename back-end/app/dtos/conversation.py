from pydantic import BaseModel, Field


class MessageSourceResponse(BaseModel):
    document_id: str
    filename: str
    url: str | None
    source_type: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[MessageSourceResponse] = Field(default_factory=list)


class ConversationSummaryResponse(BaseModel):
    id: str
    title: str


class ConversationResponse(BaseModel):
    id: str
    title: str
    messages: list[MessageResponse]
