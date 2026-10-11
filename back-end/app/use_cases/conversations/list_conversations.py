from app.models import Conversation
from app.repositories import ConversationRepository


class ListConversationsUseCase:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: str) -> list[Conversation]:
        return await self._repository.list_by_user(user_id)
