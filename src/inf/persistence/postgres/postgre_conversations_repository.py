import psycopg
from src.dom.entities.conversation import Conversation


class PostgreConversationsRepository:

    def __init__(
            self,
            connection: psycopg.Connection
    ):
        self.connection = connection

    def get_by_id(
            self,
            conversation_id: int
    ) -> Conversation | None:

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    title
                FROM conversations
                WHERE id = %s
                """,
                (
                    conversation_id,
                )
            )

            row = cursor.fetchone()

        if row is None:
            return None

        return Conversation(
            id=row[0],
            user_id=row[1],
            title=row[2]
        )

    def get_by_user_id(
            self,
            user_id: int
    ) -> list[Conversation]:

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    title
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC
                """,
                (
                    user_id,
                )
            )

            rows = cursor.fetchall()

        conversations = []

        for row in rows:
            conversations.append(
                Conversation(
                    id=row[0],
                    user_id=row[1],
                    title=row[2]
                )
            )

        return conversations

    def create(
            self,
            user_id: int,
            title: str
    ) -> Conversation:

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversations(
                    user_id,
                    title
                )
                VALUES(
                    %s,
                    %s
                )
                RETURNING
                    id,
                    user_id,
                    title
                """,
                (
                    user_id,
                    title
                )
            )

            row = cursor.fetchone()

        self.connection.commit()

        return Conversation(
            id=row[0],
            user_id=row[1],
            title=row[2]
        )

    def update_title(
            self,
            conversation_id: int,
            title: str
    ) -> Conversation | None:

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE conversations
                SET
                    title = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING
                    id,
                    user_id,
                    title
                """,
                (
                    title,
                    conversation_id
                )
            )

            row = cursor.fetchone()

        self.connection.commit()

        if row is None:
            return None

        return Conversation(
            id=row[0],
            user_id=row[1],
            title=row[2]
        )

    def delete(
            self,
            conversation_id: int
    ) -> bool:

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM conversations
                WHERE id = %s
                RETURNING id
                """,
                (
                    conversation_id,
                )
            )

            row = cursor.fetchone()

        self.connection.commit()

        return row is not None
