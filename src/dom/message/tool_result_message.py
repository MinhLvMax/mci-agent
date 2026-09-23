from dataclasses import dataclass
from src.dom.message import BaseMessage


@dataclass
class ToolResultMessage(BaseMessage):
    tool_call_id: str
    tool_result: str
    tool_name: str
