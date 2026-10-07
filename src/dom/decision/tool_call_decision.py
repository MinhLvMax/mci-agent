from dataclasses import dataclass, field
from src.dom.decision import Decision
from src.dom.tool_call import ToolCall


@dataclass
class ToolCallDecision(Decision):
    tool_calls: list[ToolCall]
    # Item riêng của nhà cung cấp model (vd reasoning của OpenAI) cần gửi lại ở lượt sau để model nhớ mạch suy nghĩ
    provider_items: list[dict] = field(default_factory=list)
