import time
import uuid
from typing import Generator, Literal

import httpx
from ollama import Client, ResponseError

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


class OllamaModelReasoner(ModelReasoner):
    CLOUD_HOST = "https://ollama.com"
    MAX_ATTEMPTS = 3  # Tổng số lần gọi khi gặp lỗi tạm thời
    RETRY_DELAY_SECONDS = 2  # Lần gọi lại thứ n chờ n * 2 giây

    def __init__(self,
                 host: str | None = None,
                 model: str | None = None,
                 api_key: str | None = None,
                 think: bool | Literal['low', 'medium', 'high'] = False):
        '''think: qwen3/deepseek nhận True/False, gpt-oss chỉ nhận 'low'/'medium'/'high' '''
        api_key = api_key or Config.OLLAMA_API_KEY
        # Có key mà không chỉ định host thì mặc định gọi lên cloud
        host = host or (self.CLOUD_HOST if api_key else Config.OLLAMA_HOST)

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None

        self.client = Client(host=host, headers=headers)
        self.model = model or "qwen3:0.6b"
        self.think = think

    def decide(self, context: Context, tools: list[Tool]) -> Decision:
        '''Chạy hết decide_stream, bỏ qua các event, chỉ lấy Decision cuối'''
        stream = self.decide_stream(context, tools)
        while True:
            try:
                next(stream)
            except StopIteration as stop:
                return stop.value

    def decide_stream(self, context: Context, tools: list[Tool]) -> Generator[AgentEvent, None, Decision]:
        messages = [
            self._convert_message(message)
            for message in context.messages
        ]

        tool_schemas = [
            self._convert_tool(tool)
            for tool in tools
        ]

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            content = ""
            raw_tool_calls = []

            try:
                stream = self.client.chat(
                    model=self.model,
                    messages=messages,
                    tools=tool_schemas,
                    think=self.think,
                    stream=True,
                )

                for chunk in stream:
                    message = chunk.message

                    if message.thinking:
                        yield AgentEvent(type='thinking', data={"text": message.thinking})

                    if message.content:
                        content += message.content
                        yield AgentEvent(type='content', data={"text": message.content})

                    if message.tool_calls:
                        raw_tool_calls.extend(message.tool_calls)

                break

            except (ResponseError, ConnectionError, httpx.TransportError) as e:
                # Lỗi tạm thời của server (500, 429, mất kết nối) thì gọi lại sau một lúc.
                # Đã trả chữ cho người dùng thì không gọi lại nữa để câu trả lời không bị lặp.
                if content or attempt == self.MAX_ATTEMPTS or not _is_transient(e):
                    raise

                delay = self.RETRY_DELAY_SECONDS * attempt
                Config.logger.warning(f'Ollama request failed ({e}), retry {attempt}/{self.MAX_ATTEMPTS - 1} in {delay}s')
                time.sleep(delay)

        if raw_tool_calls:
            tool_calls = [
                self._convert_tool_call(call)
                for call in raw_tool_calls
            ]

            return ToolCallDecision(
                tool_calls=tool_calls
            )

        return FinalDecision(
            final_content=content
        )

    def _convert_message(self, message: BaseMessage) -> dict:
        '''Chuyển đổi các message của nghiệp vụ thành dạng mà ollama hiểu và làm việc'''
        if isinstance(message, TextMessage):
            return self._convert_final_message(message)

        if isinstance(message, ToolCallMessage):
            return self._convert_tool_call_message(message)

        if isinstance(message, ToolResultMessage):
            return self._convert_tool_result_message(message)

        raise TypeError(
            f"Unsupported message type: {type(message).__name__}"
        )

    def _convert_tool(self, tool: Tool) -> dict:
        '''Chuyển tool của app thành dạng json mô tả mà Ollama hiểu và làm việc'''
        return {
            "type": "function",
            "function": {
                "name": tool.tool_name,
                "description": tool.tool_description,
                "parameters": tool.tool_kwargs.model_json_schema(),
            }
        }

    def _convert_final_message(
            self,
            message: TextMessage,
    ) -> dict:
        return {
            "role": message.role,
            "content": message.content,
        }

    def _convert_tool_result_message(
            self,
            message: ToolResultMessage,
    ) -> dict:
        # Ollama không dùng tool_call_id, nó ghép kết quả với lời gọi qua tool_name
        return {
            "role": "tool",
            "tool_name": message.tool_name,
            "content": str(message.tool_result),
        }

    def _convert_tool_call_message(
            self,
            message: ToolCallMessage,
    ) -> dict:
        # Khác Groq/OpenAI: arguments của Ollama là dict, không phải chuỗi json
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": call.name,
                        "arguments": call.kwargs,
                    }
                }
                for call in message.list_tool_call
            ]
        }

    def _convert_tool_call(self, call) -> ToolCall:
        '''
        call ở đây là call nhận từ response của ollama, chuyển nó về dạng mà app hiểu.
        Ollama không trả về id cho tool call nên tự sinh id để app ghép kết quả.
        '''
        return ToolCall(
            tool_call_id=f"call_{uuid.uuid4().hex[:12]}",
            name=call.function.name,
            kwargs=dict(call.function.arguments or {}),
        )


def _is_transient(error: Exception) -> bool:
    '''Lỗi đáng gọi lại: server lỗi 5xx, quá tải 429 hoặc lỗi kết nối'''
    if isinstance(error, ResponseError):
        return error.status_code >= 500 or error.status_code == 429
    return True
