import psycopg
from src.dom.entities.feedback import Feedback


class PostgreFeedbacksRepository:

    def __init__(
            self,
            connection: psycopg.Connection
    ):
        self.connection = connection

    def create(
            self,
            user_id: int,
            conversation_id: int | None,
            content: str
    ) -> Feedback:

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO feedbacks(
                    user_id,
                    conversation_id,
                    content
                )
                VALUES(
                    %s,
                    %s,
                    %s
                )
                RETURNING
                    id,
                    user_id,
                    conversation_id,
                    content
                """,
                (
                    user_id,
                    conversation_id,
                    content
                )
            )

            row = cursor.fetchone()

        self.connection.commit()

        return Feedback(
            id=row[0],
            user_id=row[1],
            conversation_id=row[2],
            content=row[3]
        )
