import psycopg
from src.dom.entities.memory import Memory

_COLUMNS = """
    id,
    scope,
    user_id,
    content,
    status,
    source,
    source_conversation_id,
    source_feedback_id,
    proposed_by,
    approved_by,
    created_at,
    updated_at
"""


def _to_memory(row) -> Memory:
    return Memory(
        id=row[0],
        scope=row[1],
        user_id=row[2],
        content=row[3],
        status=row[4],
        source=row[5],
        source_conversation_id=row[6],
        source_feedback_id=row[7],
        proposed_by=row[8],
        approved_by=row[9],
        created_at=row[10],
        updated_at=row[11],
    )


class PostgreMemoriesRepository:
    '''Đọc/ghi bảng memories (bộ nhớ dài hạn của agent)'''

    def __init__(self, connection: psycopg.Connection):
        self.connection = connection

    def list_for_prompt(self, user_id: int, limit_per_scope: int = 40) -> list[Memory]:
        '''
        Memory đang active dùng để ghép vào system prompt: quy định org + ghi nhớ riêng của user.
        Mỗi scope lấy tối đa limit_per_scope mục mới nhất để prompt không phình mãi.
        '''
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                (
                    SELECT {_COLUMNS} FROM memories
                    WHERE scope = 'org' AND status = 'active'
                    ORDER BY updated_at DESC
                    LIMIT %s
                )
                UNION ALL
                (
                    SELECT {_COLUMNS} FROM memories
                    WHERE scope = 'user' AND user_id = %s AND status = 'active'
                    ORDER BY updated_at DESC
                    LIMIT %s
                )
                """,
                (limit_per_scope, user_id, limit_per_scope)
            )
            rows = cursor.fetchall()

        return [_to_memory(row) for row in rows]

    def list_for_extractor(self, user_id: int) -> list[Memory]:
        '''Memory extractor cần biết để tránh trùng: như list_for_prompt, thêm các memory org đang chờ duyệt'''
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_COLUMNS} FROM memories
                WHERE (scope = 'org' AND status IN ('active', 'pending'))
                   OR (scope = 'user' AND user_id = %s AND status = 'active')
                ORDER BY scope, updated_at DESC
                LIMIT 120
                """,
                (user_id,)
            )
            rows = cursor.fetchall()

        return [_to_memory(row) for row in rows]

    def list_for_user(self, user_id: int) -> list[Memory]:
        '''Ghi nhớ riêng của user + các đề xuất org do user này tạo ra (để user tự xem)'''
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_COLUMNS} FROM memories
                WHERE status <> 'archived'
                  AND ((scope = 'user' AND user_id = %s) OR (scope = 'org' AND proposed_by = %s))
                ORDER BY updated_at DESC
                """,
                (user_id, user_id)
            )
            rows = cursor.fetchall()

        return [_to_memory(row) for row in rows]

    def list_org(self, status: str | None = None) -> list[Memory]:
        '''Memory org cho trang admin, status None thì lấy tất cả trừ archived'''
        with self.connection.cursor() as cursor:
            if status is None:
                cursor.execute(
                    f"""
                    SELECT {_COLUMNS} FROM memories
                    WHERE scope = 'org' AND status <> 'archived'
                    ORDER BY status = 'pending' DESC, updated_at DESC
                    """
                )
            else:
                cursor.execute(
                    f"""
                    SELECT {_COLUMNS} FROM memories
                    WHERE scope = 'org' AND status = %s
                    ORDER BY updated_at DESC
                    """,
                    (status,)
                )
            rows = cursor.fetchall()

        return [_to_memory(row) for row in rows]

    def get_by_id(self, memory_id: int) -> Memory | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM memories WHERE id = %s",
                (memory_id,)
            )
            row = cursor.fetchone()

        return _to_memory(row) if row else None

    def create(self, memory: Memory) -> Memory:
        # transaction(): lỗi SQL chỉ rollback phần này. Tool remember dùng chung connection với lượt chat,
        # không bọc thì lỗi ở đây làm hỏng transaction và lượt chat không lưu được tin nhắn
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO memories(
                    scope,
                    user_id,
                    content,
                    status,
                    source,
                    source_conversation_id,
                    source_feedback_id,
                    proposed_by,
                    approved_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {_COLUMNS}
                """,
                (
                    memory.scope,
                    memory.user_id,
                    memory.content,
                    memory.status,
                    memory.source,
                    memory.source_conversation_id,
                    memory.source_feedback_id,
                    memory.proposed_by,
                    memory.approved_by,
                )
            )
            row = cursor.fetchone()

        self.connection.commit()
        return _to_memory(row)

    def update_content(self, memory_id: int, content: str) -> Memory | None:
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE memories
                SET content = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING {_COLUMNS}
                """,
                (content, memory_id)
            )
            row = cursor.fetchone()

        self.connection.commit()
        return _to_memory(row) if row else None

    def set_status(self, memory_id: int, status: str, approved_by: int | None = None) -> Memory | None:
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE memories
                SET status = %s,
                    approved_by = COALESCE(%s, approved_by),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING {_COLUMNS}
                """,
                (status, approved_by, memory_id)
            )
            row = cursor.fetchone()

        self.connection.commit()
        return _to_memory(row) if row else None
