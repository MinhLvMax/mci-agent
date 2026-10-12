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
            content: str,
            rating: int | None = None,
            kind: str | None = None,
    ) -> Feedback:

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO feedbacks(
                    user_id,
                    conversation_id,
                    content,
                    rating,
                    kind
                )
                VALUES(
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING
                    id,
                    user_id,
                    conversation_id,
                    content,
                    rating,
                    kind
                """,
                (
                    user_id,
                    conversation_id,
                    content,
                    rating,
                    kind
                )
            )

            row = cursor.fetchone()

        self.connection.commit()

        return Feedback(
            id=row[0],
            user_id=row[1],
            conversation_id=row[2],
            content=row[3],
            rating=row[4],
            kind=row[5]
        )

    def mark_processed(self, feedback_id: int):
        '''Đánh dấu extractor đã đọc góp ý này'''
        with self.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE feedbacks SET processed_at = CURRENT_TIMESTAMP WHERE id = %s",
                (feedback_id,)
            )

        self.connection.commit()
