from dataclasses import dataclass


@dataclass
class Message:
    # conversation_id: str
    role: str
    content: str
    # metadata: dict
    id: int | None = None # Lúc tạo mới trả về ra mới cần

