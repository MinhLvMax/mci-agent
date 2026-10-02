from dataclasses import dataclass
from typing import Iterator
from src.app.services.agent_service import AgentService
from src.dom.agent_event import AgentEvent
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.dom.context import Context
from src.dom.message.text_message import TextMessage
from src.dom.entities.message import Message
from src.config import Config


@dataclass
class ChatUseCaseCommand:
    conversation_id: int
    messages: Message


@dataclass
class ChatUseCaseResult:
    message: Message


class ChatUseCase:
    SUMMARY_KWARGS_CHARS = 150  # Độ dài tối đa tham số mỗi bước trong tóm tắt khi bị gián đoạn
    SUMMARY_RESULT_CHARS = 200  # Độ dài tối đa phần kết quả mỗi bước

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

        try:
            yield from self._stream_and_save(command, messages, reasoning)

        except Exception as e:
            # Lỗi giữa chừng (vd model lỗi 500): vẫn lưu tin nhắn kèm tóm tắt các bước đã làm
            # để user gõ "tiếp tục" thì agent biết làm tiếp từ đâu
            interrupted_message = self._save_interrupted(command, reasoning, e)

            if interrupted_message is not None:
                yield AgentEvent(
                    type='interrupted',
                    data={"content": interrupted_message.content, "reasoning": interrupted_message.reasoning}
                )

            raise  # Router vẫn gửi event error như cũ

    def _stream_and_save(
            self,
            command: ChatUseCaseCommand,
            messages: list[Message],
            reasoning: list[dict],
    ) -> Iterator[AgentEvent]:
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

    def _save_interrupted(
            self,
            command: ChatUseCaseCommand,
            reasoning: list[dict],
            error: Exception,
    ) -> Message | None:
        '''Lưu tin nhắn user và tin nhắn assistant bị gián đoạn, lỗi khi lưu thì bỏ qua để lỗi gốc vẫn được báo'''
        assistant_message = Message(
            role="assistant",
            content=self._progress_summary(reasoning, error),
            reasoning=reasoning or None,
            interrupted=True,
        )

        try:
            self.conversation_repository.add_message(
                conversation_id=command.conversation_id,
                message=command.messages
            )
            self.conversation_repository.add_message(
                conversation_id=command.conversation_id,
                message=assistant_message
            )
        except Exception:
            Config.logger.exception('Failed to save interrupted messages')
            return None

        return assistant_message

    def _progress_summary(self, reasoning: list[dict], error: Exception) -> str:
        '''
        Tóm tắt các tool đã chạy xong. Nội dung này nằm trong lịch sử hội thoại
        nên ở lượt sau model đọc được và biết đã làm tới đâu.
        '''
        lines = [f"⚠️ Lượt trả lời bị gián đoạn do lỗi: {_shorten(str(error), 200)}"]

        done_steps = [
            step for step in reasoning
            if step["type"] == 'tool_call' and step.get("result") is not None
        ]

        if done_steps:
            lines += ["", "Các bước đã hoàn thành:"]
            for number, step in enumerate(done_steps, 1):
                kwargs = ", ".join(f"{k}={v}" for k, v in (step.get("kwargs") or {}).items())
                # Gộp các dòng đầu vì thông tin quan trọng (project, source_id...) thường ở dòng 2-3
                result = " | ".join(line.strip() for line in step["result"].splitlines() if line.strip())
                lines.append(
                    f"{number}. {step['name']}({_shorten(kwargs, self.SUMMARY_KWARGS_CHARS)})"
                    f" → {_shorten(result, self.SUMMARY_RESULT_CHARS)}"
                )
        else:
            lines += ["", "Chưa có bước nào hoàn thành."]

        lines += [
            "",
            'Gõ "tiếp tục" để agent làm tiếp từ bước dang dở (không lặp lại các bước đã xong).',
        ]

        return "\n".join(lines)


def _shorten(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"
