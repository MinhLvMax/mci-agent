import re
from dataclasses import dataclass

from src.app.ports.errors import DuplicateRecordError
from src.app.ports.repositories import UsersRepository
from src.app.ports.security import PasswordHasher
from src.dom.entities.user import User

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")  # Kiểm tra dạng "ten@mien.duoi", đủ chặn lỗi gõ nhầm
MIN_PASSWORD_LENGTH = 8  # Mật khẩu tối thiểu 8 ký tự
MAX_PASSWORD_BYTES = 72  # bcrypt chỉ xử lý tối đa 72 byte, dài hơn sẽ báo lỗi


class SignupValidationError(ValueError):
    """Email hoặc mật khẩu không hợp lệ."""


class EmailAlreadyExistsError(Exception):
    """Email đã có tài khoản."""


def validate_email(email: str) -> str:
    '''Chuẩn hóa và kiểm tra email, trả về email đã chuẩn hóa'''
    email = email.strip().lower()  # Chuẩn hóa để không có 2 tài khoản chỉ khác hoa thường

    if not EMAIL_PATTERN.match(email):  # Email sai định dạng
        raise SignupValidationError("Invalid email address")

    return email


def validate_password(password: str):
    if len(password) < MIN_PASSWORD_LENGTH:  # Mật khẩu quá ngắn
        raise SignupValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )

    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:  # Đếm theo byte vì chữ có dấu tốn 2-3 byte
        raise SignupValidationError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes"
        )


@dataclass
class SignupUserCommand:
    email: str
    password: str


@dataclass
class SignupUserResult:
    user_id: int
    email: str
    is_active: bool  # Luôn False: tài khoản phải chờ quản trị viên duyệt


class SignupUseCase:

    def __init__(
            self,
            user_repository: UsersRepository,
            password_hasher: PasswordHasher,
    ):
        self.user_repository = user_repository
        self.password_hasher = password_hasher

    def execute(
            self,
            command: SignupUserCommand
    ) -> SignupUserResult:

        email = validate_email(command.email)
        validate_password(command.password)

        if self.user_repository.get_user_by_email(email) is not None:  # Email đã được đăng ký
            raise EmailAlreadyExistsError("Email already registered")

        try:
            user = self.user_repository.create(
                User(
                    email=email,
                    password_hash=self.password_hasher.hash(command.password),  # Chỉ lưu bản băm, không lưu mật khẩu
                    is_active=False,  # Chờ quản trị viên duyệt mới đăng nhập được
                )
            )

        except DuplicateRecordError:  # Hai người đăng ký cùng email cùng lúc, lọt qua bước kiểm tra trên
            raise EmailAlreadyExistsError("Email already registered")

        return SignupUserResult(
            user_id=user.id,
            email=user.email,
            is_active=user.is_active,
        )
