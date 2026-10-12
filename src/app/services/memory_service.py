from src.app.ports.repositories import MemoriesRepository
from src.dom.entities.memory import Memory

MAX_MEMORY_CHARS = 500


class MemoryPermissionError(Exception):
    '''Memory không tồn tại hoặc không thuộc quyền của user'''


class MemoryService:
    '''
    Quy tắc ghi bộ nhớ dùng chung cho tool remember/forget và bộ trích xuất bài học:
    - scope user: active ngay, chỉ được sửa/xoá memory user của chính mình.
    - scope org: luôn tạo đề xuất pending, admin duyệt mới có hiệu lực (kể cả khi là sửa quy định cũ).
    '''

    def __init__(self, repository: MemoriesRepository):
        self.repository = repository

    def remember(
            self,
            user_id: int,
            scope: str,
            content: str,
            source: str,
            conversation_id: int | None = None,
            feedback_id: int | None = None,
            replace_memory_id: int | None = None,
    ) -> Memory:
        content = " ".join(content.split())[:MAX_MEMORY_CHARS]
        if not content:
            raise ValueError("Memory content is empty")

        if scope == 'user':
            if replace_memory_id is not None:
                old = self._get_own_user_memory(user_id, replace_memory_id)
                return self.repository.update_content(old.id, content)

            return self.repository.create(Memory(
                scope='user',
                user_id=user_id,
                content=content,
                status='active',
                source=source,
                source_conversation_id=conversation_id,
                source_feedback_id=feedback_id,
                proposed_by=user_id,
            ))

        if scope == 'org':
            if replace_memory_id is not None:
                # Ghi rõ đề xuất này thay cho quy định nào để admin xử lý quy định cũ
                content = f"{content} (thay cho #{replace_memory_id})"

            return self.repository.create(Memory(
                scope='org',
                content=content,
                status='pending',
                source=source,
                source_conversation_id=conversation_id,
                source_feedback_id=feedback_id,
                proposed_by=user_id,
            ))

        raise ValueError(f"Unknown memory scope: {scope}")

    def forget(self, user_id: int, memory_id: int) -> Memory:
        '''User chỉ tự xoá được memory riêng; memory org phải do admin xoá'''
        memory = self._get_own_user_memory(user_id, memory_id)
        return self.repository.set_status(memory.id, 'archived')

    def _get_own_user_memory(self, user_id: int, memory_id: int) -> Memory:
        memory = self.repository.get_by_id(memory_id)
        if memory is None or memory.scope != 'user' or memory.user_id != user_id or memory.status == 'archived':
            raise MemoryPermissionError(f"Memory #{memory_id} not found among this user's personal memories")
        return memory
