import psycopg

from src.dom.entities.message import Message


class PostgreMessegesRepository:

    def __init__(
            self,
            connection: psycopg.Connection
    ):
        self.connection = connection

    def get_messages(
            self,
            conversation_id: str
    ) -> list[Message]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    role,
                    content
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                """,
                (
                    conversation_id,
                )
            )

            rows = cursor.fetchall()

        messages = []

        for row in rows:
            messages.append(
                Message(
                    role=row[0],
                    content=row[1]
                )
            )

        return messages

    def add_message(
            self,
            conversation_id: str,
            message: Message
    ) -> Message:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages(
                    conversation_id,
                    role,
                    content
                )
                VALUES(
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (
                    conversation_id,
                    message.role,
                    message.content
                )
            )

        self.connection.commit()

        return message
