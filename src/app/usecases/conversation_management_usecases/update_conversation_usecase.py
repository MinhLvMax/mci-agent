from dataclasses import dataclass
from src.app.ports.repositories import ConversationsRepository


@dataclass
class UpdateConversationUseCaseCommand:
    conversation_id: int
    title: str


@dataclass
class UpdateConversationUseCaseResult:
    id: int
    user_id: int
    title: str


class UpdateConversationUsecase:
    def __init__(self, conversation_repository: ConversationsRepository):
        self.conversation_repository = conversation_repository

    def execute(self, command: UpdateConversationUseCaseCommand) -> UpdateConversationUseCaseResult:
        updated_conversation = self.conversation_repository.update_title(
            conversation_id=command.conversation_id,
            title=command.title
        )

        return UpdateConversationUseCaseResult(
            id=updated_conversation.id,
            user_id=updated_conversation.user_id,
            title=updated_conversation.title
        )
