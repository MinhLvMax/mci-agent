from dataclasses import dataclass
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository


@dataclass
class DeleteConversationUseCaseCommand:
    '''Tách ra có thêm class đầu vào đầu ra như thế này dễ đọc code hơn'''
    conversation_id: int


@dataclass
class DeleteConversationUseCaseResult:
    status: bool


class DeleteConversationUsecase:
    def __init__(self, conversation_repository: PostgreConversationsRepository):
        self.conversation_repository = conversation_repository

    def execute(self, command: DeleteConversationUseCaseCommand) -> DeleteConversationUseCaseResult:
        status = self.conversation_repository.delete(
            conversation_id=command.conversation_id,
        )

        return DeleteConversationUseCaseResult(
            status=status
        )
