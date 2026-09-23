from dataclasses import dataclass

from src.dom.repositories.user_repository import UserRepository
from src.app.services.password_hasher import PasswordHasher


@dataclass
class LoginUserCommand:
    email: str
    password: str


@dataclass
class LoginUserResult:
    user_id: int
    email: str


class LoginUserUseCase:

    def __init__(
            self,
            user_repository: UserRepository,
            password_hasher: PasswordHasher
    ):
        self.user_repository = user_repository
        self.password_hasher = password_hasher

    def execute(
            self,
            command: LoginUserCommand
    ) -> LoginUserResult:

        # Tìm user theo email
        user = self.user_repository.get_by_email(
            command.email
        )

        # Không tồn tại user
        if user is None:
            raise Exception(
                "Invalid email or password"
            )

        # Kiểm tra mật khẩu
        is_valid = self.password_hasher.verify(
            command.password,
            user.password_hash
        )

        # Sai mật khẩu
        if not is_valid:
            raise Exception(
                "Invalid email or password"
            )

        # Login thành công
        return LoginUserResult(
            user_id=user.id,
            email=user.email
        )
