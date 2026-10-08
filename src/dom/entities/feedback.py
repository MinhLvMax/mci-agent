from dataclasses import dataclass


@dataclass
class Feedback:
    id: int
    user_id: int
    conversation_id: int | None
    content: str
