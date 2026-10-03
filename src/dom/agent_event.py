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
    - interrupted: {"content", "reasoning"} lượt chạy lỗi giữa chừng, đã lưu tóm tắt các bước đã làm
    - error: {"message"}
    - title: {"title"} tên AI vừa đặt cho hội thoại sau lượt chat đầu tiên
    '''
    type: Literal['thinking', 'content', 'tool_call', 'tool_result', 'done', 'interrupted', 'error', 'title']
    data: dict

    def to_dict(self) -> dict:
        return asdict(self)
