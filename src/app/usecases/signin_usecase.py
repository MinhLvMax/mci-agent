from dataclasses import dataclass
from src.app.services.postgre_db.postgre_users_repository import PostgresUsersRepository
from src.app.services.password_hasher import PasswordHasher
from src.app.services.jwt_service import JWTService


class InactiveAccountError(Exception):
    """Đúng mật khẩu nhưng tài khoản chưa được quản trị viên kích hoạt."""


@dataclass
class SigninUserCommand:
    email: str
    password: str


@dataclass
class SigninUserResult:
    user_id: int
    email: str
    access_token: str  # JWT client phải gửi kèm ở mọi request sau khi đăng nhập
    role: str = 'user'  # UI dùng để hiện nút Quản trị, quyền thật vẫn do backend kiểm tra


class SigninUseCase:

    def __init__(
            self,
            user_repository: PostgresUsersRepository,
            jwt_service: JWTService
    ):
        self.user_repository = user_repository
        self.password_hasher = PasswordHasher()
        self.jwt_service = jwt_service  # Service tạo token, được truyền từ ngoài vào

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

        # Kiểm tra sau mật khẩu để người đoán sai không biết được trạng thái tài khoản
        if not user.is_active:  # Tài khoản chưa được duyệt hoặc đã bị khóa
            raise InactiveAccountError(
                "Account is not active"
            )

        access_token = self.jwt_service.create_access_token(  # Chỉ tạo token khi email và mật khẩu đều đúng
            user_id=user.id,  # Lưu user id vào claim "sub" của token
        )

        # Login thành công
        return SigninUserResult(
            user_id=user.id,
            email=user.email,
            access_token=access_token,  # Trả token để router gửi về client
            role=user.role
        )
