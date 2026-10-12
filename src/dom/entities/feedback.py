from dataclasses import dataclass


@dataclass
class Feedback:
    id: int
    user_id: int
    conversation_id: int | None
    content: str
    rating: int | None = None  # 1 = hài lòng, -1 = chưa hài lòng
    kind: str | None = None  # 'correction' | 'preference' | 'bug' | 'other'
