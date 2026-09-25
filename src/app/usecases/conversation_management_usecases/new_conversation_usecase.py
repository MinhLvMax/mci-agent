from datetime import datetime

from dataclasses import dataclass
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository


@dataclass
class NewConversationUseCaseCommand:
    title: str
    user_id: int


@dataclass
class NewConversationUseCaseResult:
    title: str
    conversation_id: int


class NewConversationUsecase:
    def __init__(self, conversation_repository: PostgreConversationsRepository):
        self.conversation_repository = conversation_repository

    def execute(self, command: NewConversationUseCaseCommand) -> NewConversationUseCaseResult:
        conversation_title = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        new_conversation = self.conversation_repository.create(
            user_id=command.user_id,
            title=command.title
        )

        return NewConversationUseCaseResult(
            title=conversation_title,
            conversation_id=new_conversation.id
        )
