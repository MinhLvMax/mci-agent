from dataclasses import dataclass

from src.app.services.agent import Agent
from src.dom.context import Context
from src.dom.message.text_message import TextMessage
from src.dom.repositories.conversation_repository import ConversationRepository


@dataclass
class ChatUseCaseCommand:
    conversation_id: str
    new_message: TextMessage


@dataclass
class ChatUseCaseResult:
    message: TextMessage


class ChatUseCase:

    def __init__(
            self,
            agent: Agent,
            conversation_repository: ConversationRepository
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

        # Thêm message mới vào context
        messages = history + [
            command.new_message
        ]

        # Gọi agent
        response = self.agent.invoke(
            context=Context(
                messages=messages
            )
        )

        # Tạo message assistant
        assistant_message = TextMessage(
            role="assistant",
            content=response
        )

        # Lưu cả user message và assistant message vào db
        self.conversation_repository.add_message(
            conversation_id=command.conversation_id,
            message=command.new_message
        )

        self.conversation_repository.add_message(
            conversation_id=command.conversation_id,
            message=assistant_message
        )

        return ChatUseCaseResult(
            message=assistant_message
        )
