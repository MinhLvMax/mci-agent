from src.dom.entities.user import User


class UserRepository:
    def get_by_email(self, email: str) -> User | None:
        ...

    def create(
            self,
            user: User
    ) -> User:
        ...

    def get_all(self) -> list[User]:
        ...
