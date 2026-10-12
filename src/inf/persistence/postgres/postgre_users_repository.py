import psycopg
from src.dom.entities.user import User
from src.inf.persistence.postgres.errors import translate_unique_violation


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
                    is_active,
                    role
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
            is_active=row[3],  # Trạng thái kích hoạt để đăng nhập kiểm tra
            role=row[4]
        )

    def create(
            self,
            user: User
    ) -> User:
        with translate_unique_violation(self.connection, "Email already registered"), self.connection.cursor() as cursor:
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

    def get_user_by_id(
            self,
            user_id: int
    ) -> User | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    email,
                    password_hash,
                    is_active,
                    role
                FROM users
                WHERE id = %s
                """,
                (user_id,)
            )

            row = cursor.fetchone()

        if row is None:
            return None

        return User(
            id=row[0],
            email=row[1],
            password_hash=row[2],
            is_active=row[3],
            role=row[4]
        )

    def list_all(self) -> list[User]:
        '''Toàn bộ user cho trang quản trị, tài khoản chờ duyệt đứng đầu'''
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    email,
                    password_hash,
                    is_active,
                    role,
                    created_at
                FROM users
                ORDER BY is_active ASC, created_at DESC
                """
            )

            rows = cursor.fetchall()

        return [
            User(
                id=row[0],
                email=row[1],
                password_hash=row[2],
                is_active=row[3],
                role=row[4],
                created_at=row[5],
            )
            for row in rows
        ]

    def update(
            self,
            user_id: int,
            email: str | None = None,
            role: str | None = None,
            is_active: bool | None = None,
    ) -> User | None:
        '''Chỉ ghi các cột được truyền vào (khác None)'''
        with translate_unique_violation(self.connection, "Email already registered"), self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET email = COALESCE(%s, email),
                    role = COALESCE(%s, role),
                    is_active = COALESCE(%s, is_active),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id
                """,
                (email, role, is_active, user_id)
            )

            row = cursor.fetchone()

        self.connection.commit()

        return self.get_user_by_id(row[0]) if row else None

    def set_password_hash(
            self,
            user_id: int,
            password_hash: str
    ):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (password_hash, user_id)
            )

        self.connection.commit()

    def count_active_admins(self) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM users WHERE role = 'admin' AND is_active")
            return cursor.fetchone()[0]

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
    from src.inf.persistence.postgres import create_postgres_connection
    from src.inf.security.bcrypt_password_hasher import BcryptPasswordHasher as PasswordHasher

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
