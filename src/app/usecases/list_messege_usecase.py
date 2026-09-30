from dataclasses import dataclass
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.dom.entities.message import Message


@dataclass
class ListMessegeUseCaseCommand:
    conversation_id: int


@dataclass
class ListMessegeUseCaseResult:
    messages: list[Message]


class ListMessegeUsecase:
    def __init__(self, message_repository: PostgreMessegesRepository):
        self.message_repository = message_repository

    def execute(self, command: ListMessegeUseCaseCommand) -> ListMessegeUseCaseResult:
        messeages = self.message_repository.get_messages(
            conversation_id=command.conversation_id,
        )

        return ListMessegeUseCaseResult(
            messages=messeages
        )
