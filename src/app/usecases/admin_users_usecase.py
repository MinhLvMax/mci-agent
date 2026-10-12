from dataclasses import dataclass

from src.app.ports.security import PasswordHasher
from src.app.ports.errors import DuplicateRecordError
from src.app.ports.repositories import UsersRepository
from src.app.usecases.signup_usecase import EmailAlreadyExistsError, validate_email, validate_password
from src.dom.entities.user import User

ROLES = ('user', 'admin')


class UserNotFoundError(Exception):
    """User cần sửa không tồn tại."""


class AdminRuleError(ValueError):
    """Thay đổi làm admin tự khoá mình hoặc hệ thống không còn admin nào."""


@dataclass
class UpdateUserCommand:
    actor_id: int  # Admin đang thao tác
    user_id: int  # User bị sửa
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None


class AdminUsersUsecase:
    '''Nghiệp vụ trang quản trị người dùng: kích hoạt/khoá, đổi email, đổi quyền, đặt lại mật khẩu'''

    def __init__(self, user_repository: UsersRepository, password_hasher: PasswordHasher):
        self.user_repository = user_repository
        self.password_hasher = password_hasher

    def list_users(self) -> list[User]:
        return self.user_repository.list_all()

    def update_user(self, command: UpdateUserCommand) -> User:
        user = self.user_repository.get_user_by_id(command.user_id)
        if user is None:
            raise UserNotFoundError(f"User {command.user_id} not found")

        if command.role is not None and command.role not in ROLES:
            raise AdminRuleError(f"Invalid role: {command.role}")

        email = None
        if command.email is not None:
            email = validate_email(command.email)
            other = self.user_repository.get_user_by_email(email)
            if other is not None and other.id != user.id:
                raise EmailAlreadyExistsError("Email already registered")

        loses_admin = user.role == 'admin' and user.is_active and (
                (command.role is not None and command.role != 'admin')
                or command.is_active is False
        )

        if loses_admin:
            # Không cho tự hạ quyền/tự khoá để admin không lỡ tay đuổi mình ra khỏi trang quản trị
            if user.id == command.actor_id:
                raise AdminRuleError("You cannot remove your own admin access")

            if self.user_repository.count_active_admins() <= 1:
                raise AdminRuleError("The system must keep at least one active admin")

        try:
            return self.user_repository.update(
                user_id=user.id,
                email=email,
                role=command.role,
                is_active=command.is_active,
            )
        except DuplicateRecordError:  # Hai admin đổi sang cùng email cùng lúc
            raise EmailAlreadyExistsError("Email already registered")

    def reset_password(self, user_id: int, new_password: str):
        if self.user_repository.get_user_by_id(user_id) is None:
            raise UserNotFoundError(f"User {user_id} not found")

        validate_password(new_password)
        self.user_repository.set_password_hash(user_id, self.password_hasher.hash(new_password))
