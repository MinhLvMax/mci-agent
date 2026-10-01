import psycopg
from psycopg.types.json import Jsonb

from src.dom.entities.message import Message


class PostgreMessegesRepository:

    def __init__(
            self,
            connection: psycopg.Connection
    ):
        self.connection = connection

    def get_messages(
            self,
            conversation_id: int
    ) -> list[Message]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    role,
                    content,
                    metadata
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
            metadata = row[2] or {}  # psycopg tự đọc JSONB thành dict, tin nhắn cũ thì là NULL
            messages.append(
                Message(
                    role=row[0],
                    content=row[1],
                    reasoning=metadata.get("reasoning"),
                )
            )

        return messages

    def add_message(
            self,
            conversation_id: int,
            message: Message
    ) -> Message:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages(
                    conversation_id,
                    role,
                    content,
                    metadata
                )
                VALUES(
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (
                    conversation_id,
                    message.role,
                    message.content,
                    self._to_metadata(message),
                )
            )

        self.connection.commit()

        return message

    def _to_metadata(self, message: Message) -> Jsonb | None:
        '''
        Gom các thông tin phụ của message vào cột metadata (JSONB).
        Sau này muốn lưu thêm (model, token...) thì thêm key vào đây.
        '''
        metadata = {}
        if message.reasoning:
            metadata["reasoning"] = message.reasoning
        return Jsonb(metadata) if metadata else None
