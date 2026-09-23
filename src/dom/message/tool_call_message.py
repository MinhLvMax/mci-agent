from dataclasses import dataclass
from src.dom.message import BaseMessage
from src.dom.tool_call import ToolCall


@dataclass
class ToolCallMessage(BaseMessage):
    list_tool_call: list[ToolCall]
