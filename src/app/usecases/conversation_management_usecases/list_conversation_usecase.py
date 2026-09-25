from dataclasses import dataclass
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.dom.entities.conversation import Conversation


@dataclass
class ListConversationUseCaseCommand:
    '''Tách ra có thêm class đầu vào đầu ra như thế này dễ đọc code hơn'''
    user_id: int


@dataclass
class ListConversationUseCaseResult:
    conversations: list[Conversation]


class ListConversationUsecase:
    def __init__(self, conversation_repository: PostgreConversationsRepository):
        self.conversation_repository = conversation_repository

    def execute(self, command: ListConversationUseCaseCommand) -> ListConversationUseCaseResult:
        conversations = self.conversation_repository.get_by_user_id(
            user_id=command.user_id,
        )

        return ListConversationUseCaseResult(
            conversations=conversations
        )
