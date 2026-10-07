from dataclasses import dataclass, field
from src.dom.message import BaseMessage
from src.dom.tool_call import ToolCall


@dataclass
class ToolCallMessage(BaseMessage):
    list_tool_call: list[ToolCall]
    provider_items: list[dict] = field(default_factory=list)  # Chỉ sống trong một lượt chạy, không lưu DB
