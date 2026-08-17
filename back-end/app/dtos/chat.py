from typing import Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str


class SendMessageRequest(BaseModel):
    messages: list[ChatMessage] | None = None
    message: str | None = None
    conversation_id: str | None = None

    def sanitized_message(self) -> str:
        if self.message is not None:
            return self.message.strip()

        if self.messages:
            last_user_message = next(
                (
                    message
                    for message in reversed(self.messages)
                    if message.role == "user" and message.content.strip()
                ),
                None,
            )
            if last_user_message:
                return last_user_message.content.strip()

        return ""
