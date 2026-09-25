from dataclasses import dataclass
from src.app.services.agent import Agent
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.dom.context import Context
from src.dom.message.text_message import TextMessage
from src.dom.entities.message import Message


@dataclass
class ChatUseCaseCommand:
    conversation_id: int
    messages: list[Message]


@dataclass
class ChatUseCaseResult:
    message: Message


class ChatUseCase:

    def __init__(
            self,
            agent: Agent,
            conversation_repository: PostgreMessegesRepository
    ):
        self.agent = agent
        self.conversation_repository = conversation_repository

    def execute(
            self,
            command: ChatUseCaseCommand
    ) -> ChatUseCaseResult:
        # Lấy lịch sử hội thoại
        history = self.conversation_repository.get_messages(
            conversation_id=command.conversation_id
        )

        # Thêm message mới vào lịch sử
        messages = history + [
            command.messages
        ]

        # Gọi agent
        response = self.agent.invoke(
            context=Context(
                messages=[
                    TextMessage(  # Phải chuyển về dạng text mà agent cần
                        role=m.role,
                        content=m.content,
                    ) for m in messages
                ]
            )
        )

        # Tạo message assistant
        assistant_message = Message(
            role="assistant",
            content=response
        )

        # Lưu cả user message và assistant message vào db
        self.conversation_repository.add_message(
            conversation_id=command.conversation_id,
            message=command.messages
        )

        self.conversation_repository.add_message(
            conversation_id=command.conversation_id,
            message=assistant_message
        )

        return ChatUseCaseResult(
            message=assistant_message
        )
