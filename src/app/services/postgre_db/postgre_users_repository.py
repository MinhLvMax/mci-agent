import psycopg
from src.dom.entities.user import User


class PostgresUsersRepository:

    def __init__(self, connection: psycopg.Connection):
        self.connection = connection

    def get_user_by_email(
            self,
            email: str
    ) -> User | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    email,
                    password_hash,
                    is_active
                FROM users
                WHERE lower(email) = lower(%s)
                """,  # So sánh không phân biệt hoa thường: "A@x.com" và "a@x.com" là một tài khoản
                (email.strip(),)  # Bỏ khoảng trắng thừa user lỡ gõ
            )

            row = cursor.fetchone()

        if row is None:
            return None

        return User(
            id=row[0],
            email=row[1],
            password_hash=row[2],
            is_active=row[3]  # Trạng thái kích hoạt để đăng nhập kiểm tra
        )

    def create(
            self,
            user: User
    ) -> User:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users(
                    email,
                    password_hash,
                    is_active
                )
                VALUES(%s, %s, %s)
                RETURNING id
                """,  # Ghi rõ is_active thay vì dựa vào mặc định của DB
                (
                    user.email,
                    user.password_hash,
                    user.is_active
                )
            )

            user.id = cursor.fetchone()[0]

        self.connection.commit()

        return user

    def get_all(self) -> list[User]:

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    email,
                    password_hash
                FROM users
                ORDER BY id ASC
                """
            )

            rows = cursor.fetchall()

        users = []

        for row in rows:
            users.append(
                User(
                    email=row[1],
                    password_hash=row[2],
                    id=row[0]
                )
            )

        return users


if __name__ == '__main__':
    from src.app.services.postgre_db import create_postgres_connection
    from src.app.services.password_hasher import PasswordHasher

    hasher = PasswordHasher()
    conn = create_postgres_connection()
    repo = PostgresUsersRepository(
        connection=conn
    )

    repo.create(
        User(
            email='Minh',
            password_hash=hasher.hash('minh123')
        )
    )
    print(repo.get_all())
