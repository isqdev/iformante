from pydantic import BaseModel


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str


class ConversationSummaryResponse(BaseModel):
    id: str
    title: str


class ConversationResponse(BaseModel):
    id: str
    title: str
    messages: list[MessageResponse]
