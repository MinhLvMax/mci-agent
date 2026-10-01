import uuid
from typing import Generator, Literal
from ollama import Client

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

        stream = self.client.chat(
            model=self.model,
            messages=messages,
            tools=tool_schemas,
            think=self.think,
            stream=True,
        )

        content = ""
        raw_tool_calls = []

        for chunk in stream:
            message = chunk.message

            if message.thinking:
                yield AgentEvent(type='thinking', data={"text": message.thinking})

            if message.content:
                content += message.content
                yield AgentEvent(type='content', data={"text": message.content})

            if message.tool_calls:
                raw_tool_calls.extend(message.tool_calls)

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
