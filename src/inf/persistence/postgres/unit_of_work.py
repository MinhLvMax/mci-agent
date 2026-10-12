from typing import Self

from src.inf.persistence.postgres.connection import create_postgres_connection
from src.inf.persistence.postgres.postgre_conversations_repository import PostgreConversationsRepository
from src.inf.persistence.postgres.postgre_feedbacks_repository import PostgreFeedbacksRepository
from src.inf.persistence.postgres.postgre_files_repository import PostgreFilesRepository
from src.inf.persistence.postgres.postgre_memories_repository import PostgreMemoriesRepository
from src.inf.persistence.postgres.postgre_messages_repository import PostgreMessegesRepository
from src.inf.persistence.postgres.postgre_skills_repository import PostgreSkillsRepository
from src.inf.persistence.postgres.postgre_users_repository import PostgresUsersRepository


class PostgresUnitOfWork:
    '''
    Triển khai port UnitOfWork (src/app/ports/unit_of_work.py) bằng PostgreSQL.

    Mỗi phiên mở một connection, mọi repository trong phiên dùng chung connection đó.
    Các repository tự commit sau mỗi lệnh ghi như trước, phiên chỉ lo mở/đóng và rollback khi lỗi.
    '''

    def __init__(self, connection_factory=create_postgres_connection):
        self._connection_factory = connection_factory
        self.connection = None

    def __enter__(self) -> Self:
        self.connection = self._connection_factory()

        self.users = PostgresUsersRepository(self.connection)
        self.conversations = PostgreConversationsRepository(self.connection)
        self.messages = PostgreMessegesRepository(self.connection)
        self.files = PostgreFilesRepository(self.connection)
        self.skills = PostgreSkillsRepository(self.connection)
        self.memories = PostgreMemoriesRepository(self.connection)
        self.feedbacks = PostgreFeedbacksRepository(self.connection)

        return self

    def rollback(self) -> None:
        self.connection.rollback()

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is not None:
                self.connection.rollback()  # Lệnh ghi dở dang không được commit nửa vời
        finally:
            self.connection.close()
