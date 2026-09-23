from src.dom.entities.user import User
from src.dom.repositories.user_repository import UserRepository


class PostgresUserRepository(UserRepository):

    def __init__(self, connection):
        self.connection = connection

    def get_by_email(
            self,
            email: str
    ) -> User | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    email,
                    password_hash
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            row = cursor.fetchone()

        if row is None:
            return None

        return User(
            id=row[0],
            email=row[1],
            password_hash=row[2]
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
                    password_hash
                )
                VALUES(%s, %s)
                RETURNING id
                """,
                (
                    user.email,
                    user.password_hash
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
    from src.inf.database.postgre.connection import DatabaseConnection

    dbc = DatabaseConnection()
    con = dbc.connect()
    pur = PostgresUserRepository(
        connection=con
    )
    
    pur.create(
        User(
            email='Minh',
            password_hash='hash123'
        )
    )
    print(pur.get_all())
