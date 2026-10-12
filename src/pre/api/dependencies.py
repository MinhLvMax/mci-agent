from fastapi import Depends, HTTPException  # Depends để khai báo dependency, HTTPException để trả lỗi
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # Công cụ đọc header Authorization

from src.app.ports.repositories import ConversationsRepository, UsersRepository
from src.app.ports.security import InvalidTokenError, TokenExpiredError
from src.app.ports.unit_of_work import UnitOfWork
from src.dom.entities.conversation import Conversation
from src.dom.entities.file import File
from src.pre.api.container import ApiContainer, get_container

# auto_error=False để tự trả lỗi 401 có thông báo rõ ràng thay vì lỗi mặc định
bearer_scheme = HTTPBearer(auto_error=False)  # Đọc header dạng "Authorization: Bearer <token>"


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(  # Tạo lỗi 401 dùng chung cho mọi trường hợp token không hợp lệ
        status_code=401,  # 401 = chưa xác thực
        detail=detail,  # Lý do cụ thể để client biết
        headers={"WWW-Authenticate": "Bearer"},  # Header chuẩn báo client cần gửi Bearer token
    )


def get_current_user_id(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # FastAPI tự đọc header vào đây
        container: ApiContainer = Depends(get_container),
) -> int:
    """
    Dependency gắn vào các router cần đăng nhập.

    Trả về user_id lấy từ token đã được kiểm tra chữ ký và hạn dùng.
    Router dùng giá trị này thay cho user_id do client tự gửi lên.
    """

    if credentials is None:  # Request không có header Authorization
        raise _unauthorized("Missing access token")  # Chưa đăng nhập thì từ chối

    try:
        user_id = container.token_service().decode_access_token(  # Kiểm tra chữ ký, hạn dùng rồi lấy user id
            credentials.credentials  # Phần token nằm sau chữ "Bearer "
        )

    except TokenExpiredError:  # Token đúng chữ ký nhưng đã quá hạn
        raise _unauthorized("Access token expired")  # Client cần đăng nhập lại

    except InvalidTokenError:  # Token bị sửa, sai chữ ký hoặc sai định dạng
        raise _unauthorized("Invalid access token")  # Không tin token này

    # Token còn hạn nhưng admin đã khoá tài khoản thì cũng đẩy ra ngay, không chờ token hết hạn
    with container.unit_of_work() as uow:
        user = uow.users.get_user_by_id(user_id)

    if user is None or not user.is_active:
        raise _unauthorized("Account is disabled")

    return user_id


def require_admin(
        user_id: int = Depends(get_current_user_id),
        container: ApiContainer = Depends(get_container),
) -> int:
    """Dependency cho các route quản trị: chỉ admin đang hoạt động mới qua, còn lại 403"""
    with container.unit_of_work() as uow:
        allowed = is_admin(uow.users, user_id)

    if not allowed:
        raise HTTPException(status_code=403, detail="Admin only")

    return user_id


def is_admin(users: UsersRepository, user_id: int) -> bool:
    '''Quyền admin đọc từ DB mỗi lần (token chỉ chứa user_id), đổi role trong DB là có hiệu lực ngay'''
    user = users.get_user_by_id(user_id)
    return user is not None and user.is_active and user.role == 'admin'


def get_owned_conversation(
        repository: ConversationsRepository,
        conversation_id: int,
        user_id: int,
) -> Conversation:
    """
    Lấy conversation và đảm bảo nó thuộc về user đang đăng nhập.

    Trả 404 cho cả hai trường hợp "không tồn tại" và "của người khác"
    để người ngoài không dò được id nào đang tồn tại.
    """

    conversation = repository.get_by_id(  # Tìm conversation trong DB
        conversation_id=conversation_id
    )

    if conversation is None or conversation.user_id != user_id:  # Không có hoặc không phải của user này
        raise HTTPException(  # Từ chối như thể conversation không tồn tại
            status_code=404,
            detail="Conversation not found",
        )

    return conversation  # Hợp lệ thì trả conversation cho router dùng tiếp


def get_owned_file(
        uow: UnitOfWork,
        file_id: int,
        user_id: int,
) -> tuple[File, Conversation]:
    """
    Lấy file kèm conversation chứa nó, đảm bảo conversation thuộc về user đang đăng nhập.
    File của người khác trả 404 giống file không tồn tại để không lộ thông tin.
    """

    file = uow.files.get_by_id(file_id=file_id)
    conversation = uow.conversations.get_by_id(conversation_id=file.conversation_id) if file else None

    if conversation is None or conversation.user_id != user_id:
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    return file, conversation
