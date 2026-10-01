from dataclasses import dataclass


@dataclass
class Message:
    # conversation_id: str
    role: str
    content: str
    # metadata: dict
    id: int | None = None # Lúc tạo mới trả về ra mới cần
    reasoning: list[dict] | None = None  # Các bước suy luận/gọi tool của assistant, chỉ để hiển thị

