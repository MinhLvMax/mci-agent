from dataclasses import dataclass
from src.app.services.postgre_db.postgre_users_repository import PostgresUsersRepository
from src.app.services.password_hasher import PasswordHasher
from src.app.services.jwt_service import JWTService


@dataclass
class SigninUserCommand:
    email: str
    password: str


@dataclass
class SigninUserResult:
    user_id: int
    email: str
    # access_token: str


class SigninUseCase:

    def __init__(
            self,
            user_repository: PostgresUsersRepository,
            # jwt_service: JWTService
    ):
        self.user_repository = user_repository
        self.password_hasher = PasswordHasher()
        # self.jwt_service = jwt_service

    def execute(
            self,
            command: SigninUserCommand
    ) -> SigninUserResult:

        # Tìm user theo email
        user = self.user_repository.get_user_by_email(
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

        # access_token = self.jwt_service.create_access_token(
        #     user_id=user.id,
        # )

        # Login thành công
        return SigninUserResult(
            user_id=user.id,
            email=user.email,
            # access_token=access_token
        )
