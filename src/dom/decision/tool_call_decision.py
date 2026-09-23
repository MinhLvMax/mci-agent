from dataclasses import dataclass
from src.dom.decision import Decision
from src.dom.tool_call import ToolCall


@dataclass
class ToolCallDecision(Decision):
    tool_calls: list[ToolCall]
