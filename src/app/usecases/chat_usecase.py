from dataclasses import dataclass
from typing import Iterator
from src.app.services.agent_service import AgentService
from src.dom.agent_event import AgentEvent
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.dom.context import Context
from src.dom.message.text_message import TextMessage
from src.dom.entities.message import Message


@dataclass
class ChatUseCaseCommand:
    conversation_id: int
    messages: Message


@dataclass
class ChatUseCaseResult:
    message: Message


class ChatUseCase:

    def __init__(
            self,
            agent: AgentService,
            conversation_repository,
            system_prompt: str | None = None,  # Dựng từ các skill admin cấu hình, None thì không gửi
    ):
        self.agent = agent
        self.conversation_repository = conversation_repository
        self.system_prompt = system_prompt

    def _build_context(self, messages: list[Message]) -> Context:
        '''Chuyển lịch sử về dạng text agent cần, system prompt đứng đầu và không lưu vào DB'''
        context_messages = [
            TextMessage(
                role=m.role,
                content=m.content,
            ) for m in messages
        ]

        if self.system_prompt:
            context_messages.insert(0, TextMessage(role='system', content=self.system_prompt))

        return Context(messages=context_messages)

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
            context=self._build_context(messages)
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

    def execute_stream(
            self,
            command: ChatUseCaseCommand
    ) -> Iterator[AgentEvent]:
        '''
        Giống execute nhưng yield dần các event của agent cho UI,
        đồng thời gom các bước suy luận để lưu kèm message assistant.
        '''
        history = self.conversation_repository.get_messages(
            conversation_id=command.conversation_id
        )

        messages = history + [
            command.messages
        ]

        reasoning: list[dict] = []  # [{"type": "thinking", "text"}, {"type": "tool_call", "id", "name", "kwargs", "result"}]

        for event in self.agent.invoke_stream(
                context=self._build_context(messages)
        ):
            if event.type == 'thinking':
                # Các mẩu thinking liền nhau gộp thành một bước
                if reasoning and reasoning[-1]["type"] == 'thinking':
                    reasoning[-1]["text"] += event.data["text"]
                else:
                    reasoning.append({"type": "thinking", "text": event.data["text"]})

            elif event.type == 'tool_call':
                reasoning.append({"type": "tool_call", **event.data, "result": None})

            elif event.type == 'tool_result':
                for step in reasoning:
                    if step["type"] == 'tool_call' and step["id"] == event.data["id"]:
                        step["result"] = event.data["result"]

            elif event.type == 'done':
                assistant_message = Message(
                    role="assistant",
                    content=event.data["content"],
                    reasoning=reasoning or None,
                )

                self.conversation_repository.add_message(
                    conversation_id=command.conversation_id,
                    message=command.messages
                )

                self.conversation_repository.add_message(
                    conversation_id=command.conversation_id,
                    message=assistant_message
                )

                # Lưu DB xong mới báo done, để UI reload là thấy ngay
                event = AgentEvent(
                    type='done',
                    data={"content": assistant_message.content, "reasoning": assistant_message.reasoning}
                )

            yield event
