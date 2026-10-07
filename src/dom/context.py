from dataclasses import dataclass
from src.dom.message import BaseMessage
from src.dom.message.text_message import TextMessage
from src.dom.message.tool_call_message import ToolCallMessage
from src.dom.message.tool_result_message import ToolResultMessage
from src.dom.tool_call import ToolCall


@dataclass
class Context:
    messages: list[BaseMessage]

    def add_final_message(self, content: str):
        self.messages.append(
            TextMessage(
                role='assistant',
                content=content
            )
        )

    def add_tool_call_message(self, tool_calls: list[ToolCall], provider_items: list[dict] = ()):
        self.messages.append(
            ToolCallMessage(
                role='assistant',
                list_tool_call=tool_calls,
                provider_items=list(provider_items)
            )
        )

    def add_tool_result_message(
            self,
            id: str,
            result: str,
            tool_name: str
    ):
        self.messages.append(
            ToolResultMessage(
                role='tool',
                tool_call_id=id,
                tool_result=result,
                tool_name=tool_name
            )
        )
