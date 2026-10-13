from typing import Generator

from anthropic import Anthropic, APIStatusError

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.context import Context
from src.dom.decision import Decision
from src.dom.tool import Tool
from src.dom.message import BaseMessage
from src.dom.message.text_message import TextMessage
from src.dom.message.tool_call_message import ToolCallMessage
from src.dom.message.tool_result_message import ToolResultMessage
from src.dom.tool_call import ToolCall
from src.dom.decision.tool_call_decision import ToolCallDecision
from src.dom.decision.final_decision import FinalDecision
from src.dom.agent_event import AgentEvent
from src.config import Config
from src.inf.model_reasoner.errors import translate_api_error

REFUSAL_MESSAGE = "Claude đã từ chối trả lời yêu cầu này vì lý do an toàn. Hãy diễn đạt lại yêu cầu hoặc chọn model khác."


class AnthropicModelReasoner(ModelReasoner):
    '''
    Adapter gọi model Claude qua Messages API của Anthropic.

    Chế độ suy luận là mức effort của Claude ('low' / 'medium' / 'high' / 'xhigh' / 'max', tuỳ model):
    có chế độ thì bật adaptive thinking kèm effort, None thì để model chạy mặc định.
    '''

    # Mã lưu ở cột models.provider và tên hiển thị trên giao diện: nguồn duy nhất, giao diện lấy qua API
    PROVIDER = "anthropic"
    PROVIDER_LABEL = "Anthropic"

    MAX_TOKENS = 64000  # Gọi bằng streaming nên đặt rộng được, câu trả lời dài không bị cắt giữa chừng

    def __init__(
            self,
            api_key: str | None = None,
            model: str | None = None,
            reasoning_effort: str | None = None,
    ):
        self.client = Anthropic(
            api_key=api_key or Config.ANTHROPIC_API_KEY
        )
        self.model = model or "claude-opus-5-5"
        self.reasoning_effort = reasoning_effort

    def decide(self, context: Context, tools: list[Tool]) -> Decision:
        '''Chạy hết decide_stream, bỏ qua các event, chỉ lấy Decision cuối'''
        stream = self.decide_stream(context, tools)
        while True:
            try:
                next(stream)
            except StopIteration as stop:
                return stop.value

    def decide_stream(self, context: Context, tools: list[Tool]) -> Generator[AgentEvent, None, Decision]:
        system, messages = self._convert_messages(context.messages)

        params = dict(
            model=self.model,
            max_tokens=self.MAX_TOKENS,
            messages=messages,
        )
        if system:
            params["system"] = system
        if tools:
            # Không đặt tool_choice: mặc định auto, các model Claude mới trả 400 với 'any' / 'tool'
            params["tools"] = [self._convert_tool(tool) for tool in tools]
        if self.reasoning_effort:
            # display "summarized" để UI hiện tóm tắt suy nghĩ, mặc định của các model mới là để trống
            params["thinking"] = {"type": "adaptive", "display": "summarized"}
            params["output_config"] = {"effort": self.reasoning_effort}

        try:
            with self.client.messages.stream(**params) as stream:
                for event in stream:
                    if event.type != "content_block_delta":
                        continue
                    if event.delta.type == "thinking_delta" and event.delta.thinking:
                        yield AgentEvent(type='thinking', data={"text": event.delta.thinking})
                    elif event.delta.type == "text_delta" and event.delta.text:
                        yield AgentEvent(type='content', data={"text": event.delta.text})

                response = stream.get_final_message()

        except APIStatusError as e:
            raise translate_api_error(e, "Anthropic", self.model, self.reasoning_effort) from e

        return self._to_decision(response)

    def _to_decision(self, response) -> Decision:
        if response.stop_reason == "refusal":
            # Bị từ chối có thể cắt ngang cả tool_use đang viết dở, không chạy gì cả
            return FinalDecision(final_content=REFUSAL_MESSAGE)

        tool_uses = [block for block in response.content if block.type == "tool_use"]

        if tool_uses:
            if response.stop_reason == "max_tokens":
                raise RuntimeError("Claude hết giới hạn token khi đang viết tham số tool, tham số bị cắt nên không chạy tool")

            return ToolCallDecision(
                tool_calls=[
                    ToolCall(tool_call_id=block.id, name=block.name, kwargs=dict(block.input))
                    for block in tool_uses
                ],
                # Gửi lại nguyên vẹn cả lượt (kể cả block thinking có chữ ký) ở lượt sau,
                # Claude mới tiếp tục được mạch suy nghĩ khi đã gọi tool
                provider_items=[block.to_dict() for block in response.content],
            )

        return FinalDecision(
            final_content="".join(block.text for block in response.content if block.type == "text")
        )

    # =========================================================
    # MESSAGE MAPPER
    # =========================================================

    def _convert_messages(self, messages: list[BaseMessage]) -> tuple[str, list[dict]]:
        '''
        Đổi lịch sử của app thành (system, messages) của Messages API:
        - message system gộp vào tham số system riêng;
        - các kết quả tool liên tiếp gộp vào một message user, đúng cách Claude trả nhiều tool_use cùng lúc.
        '''
        system_parts = []
        converted = []

        for message in messages:
            if isinstance(message, TextMessage) and message.role == 'system':
                system_parts.append(message.content)

            elif isinstance(message, TextMessage):
                converted.append({"role": message.role, "content": message.content})

            elif isinstance(message, ToolCallMessage):
                converted.append({"role": "assistant", "content": self._convert_tool_call_message(message)})

            elif isinstance(message, ToolResultMessage):
                block = {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": str(message.tool_result),
                }
                previous = converted[-1] if converted else None
                if previous and previous["role"] == "user" and isinstance(previous["content"], list):
                    previous["content"].append(block)
                else:
                    converted.append({"role": "user", "content": [block]})

            else:
                raise TypeError(f"Unsupported message type: {type(message).__name__}")

        return "\n\n".join(system_parts), converted

    @staticmethod
    def _convert_tool_call_message(message: ToolCallMessage) -> list[dict]:
        if message.provider_items:
            return list(message.provider_items)

        return [
            {"type": "tool_use", "id": call.tool_call_id, "name": call.name, "input": call.kwargs}
            for call in message.list_tool_call
        ]

    @staticmethod
    def _convert_tool(tool: Tool) -> dict:
        return {
            "name": tool.tool_name,
            "description": tool.tool_description,
            "input_schema": tool.tool_kwargs.model_json_schema(),
        }
