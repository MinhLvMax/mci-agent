from dataclasses import dataclass
from datetime import datetime
from typing import Literal

MemoryScope = Literal['user', 'org']
MemoryStatus = Literal['active', 'pending', 'rejected', 'archived']


@dataclass
class Memory:
    '''
    Một bài học agent ghi nhớ lâu dài, được ghép vào system prompt ở các lượt chat sau.

    scope = 'user': sở thích riêng của user_id, active ngay khi tạo.
    scope = 'org': áp dụng cho cả công ty, tạo ra ở trạng thái pending và chỉ vào prompt khi admin duyệt.
    '''
    scope: MemoryScope
    content: str
    status: MemoryStatus
    source: str  # 'tool' | 'extractor' | 'feedback' | 'admin'
    user_id: int | None = None
    source_conversation_id: int | None = None
    source_feedback_id: int | None = None
    proposed_by: int | None = None
    approved_by: int | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
