from dataclasses import dataclass, asdict
from typing import Literal


@dataclass
class AgentEvent:
    '''
    Sự kiện agent phát ra trong lúc chạy, để các lớp trên hiển thị dần.
    - thinking / content: {"text": mẩu chữ mới}
    - tool_call: {"id", "name", "kwargs"}
    - tool_result: {"id", "name", "result"}
    - done: {"content", "reasoning"}
    - error: {"message"}
    '''
    type: Literal['thinking', 'content', 'tool_call', 'tool_result', 'done', 'error']
    data: dict

    def to_dict(self) -> dict:
        return asdict(self)
