import json
from typing import Generator
from groq import Groq

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


class GroqModelReasoner(ModelReasoner):
    def __init__(self,
                 api_key: str | None = None,
                 model: str | None = None):
        api_key = api_key or Config.GROQ_API_KEY
        self.client = Groq(
            api_key=api_key
        )
        self.model = model or "openai/gpt-oss-20b"

    def decide(self, context: Context, tools: list[Tool]) -> Decision:
        messages = [
            self._convert_message(message)
            for message in context.messages
        ]

        tool_schemas = [
            self._convert_tool(tool)
            for tool in tools
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
        )

        message = response.choices[0].message

        if message.tool_calls:
            tool_calls = [
                self._convert_tool_call(call)
                for call in message.tool_calls
            ]

            return ToolCallDecision(
                tool_calls=tool_calls
            )

        return FinalDecision(
            final_content=message.content or ""
        )

    def decide_stream(self, context: Context, tools: list[Tool]) -> Generator[AgentEvent, None, Decision]:
        '''Chưa stream với Groq: gọi decide như cũ, không phát event thinking nào'''
        return self.decide(context, tools)
        yield  # Có yield thì Python mới coi hàm này là generator

    def _convert_message(self, message: BaseMessage) -> dict:
        '''Chuyển đổi các message của nghiệp vụ thành dạng mà groq hiểu và làm việc'''
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
        '''Chuyển tool của app thành dạng json mô tả mà Groq nhầm và làm việc'''
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
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            'name': message.tool_name,
            "content": message.tool_result,
        }

    def _convert_tool_call_message(
            self,
            message: ToolCallMessage,
    ) -> dict:
        return {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": call.tool_call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.kwargs),
                    }
                }
                for call in message.list_tool_call
            ]
        }

    def _convert_tool_call(self, call) -> ToolCall:
        '''
        call ở đây là call nhận từ request của groq, chuyển nó về dạng mà app hiểu
        '''
        return ToolCall(
            tool_call_id=call.id,
            name=call.function.name,
            kwargs=json.loads(
                call.function.arguments
            ),
        )
