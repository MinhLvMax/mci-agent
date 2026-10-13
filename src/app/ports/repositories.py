'''
Port lưu trữ dữ liệu của tầng app.

Use case và service chỉ phụ thuộc vào các Protocol ở đây, không biết dữ liệu nằm ở PostgreSQL hay đâu khác.
Adapter cụ thể (vd PostgreSQL) nằm ở tầng inf và tự triển khai các Protocol này.
'''
from typing import Protocol

from src.dom.entities.ai_model import AIModel
from src.dom.entities.conversation import Conversation
from src.dom.entities.feedback import Feedback
from src.dom.entities.file import File
from src.dom.entities.memory import Memory
from src.dom.entities.message import Message
from src.dom.entities.skill import Skill
from src.dom.entities.user import User


class UsersRepository(Protocol):
    def get_user_by_email(self, email: str) -> User | None:
        '''Tìm theo email, không phân biệt hoa thường'''

    def get_user_by_id(self, user_id: int) -> User | None: ...

    def create(self, user: User) -> User:
        '''Email đã tồn tại thì raise DuplicateRecordError'''

    def list_all(self) -> list[User]:
        '''Toàn bộ user, tài khoản chờ duyệt đứng đầu'''

    def update(
            self,
            user_id: int,
            email: str | None = None,
            role: str | None = None,
            is_active: bool | None = None,
    ) -> User | None:
        '''Chỉ ghi các trường khác None. Email trùng thì raise DuplicateRecordError'''

    def set_password_hash(self, user_id: int, password_hash: str) -> None: ...

    def count_active_admins(self) -> int: ...


class ConversationsRepository(Protocol):
    def get_by_id(self, conversation_id: int) -> Conversation | None: ...

    def get_by_user_id(self, user_id: int) -> list[Conversation]: ...

    def create(self, user_id: int, title: str) -> Conversation: ...

    def update_title(self, conversation_id: int, title: str) -> Conversation | None: ...

    def delete(self, conversation_id: int) -> bool: ...


class MessagesRepository(Protocol):
    def get_messages(self, conversation_id: int) -> list[Message]:
        '''Lịch sử hội thoại theo thứ tự thời gian'''

    def add_message(self, conversation_id: int, message: Message) -> Message: ...


class FilesRepository(Protocol):
    '''Metadata file trong workspace, không đọc/ghi file vật lý'''

    def get_by_id(self, file_id: int) -> File | None: ...

    def get_by_conversation_id(self, conversation_id: int) -> list[File]: ...

    def get_children(self, conversation_id: int, parent_id: int | None = None) -> list[File]: ...

    def get_by_path(self, conversation_id: int, path: str) -> File | None: ...

    def create(
            self,
            conversation_id: int,
            name: str,
            path: str,
            parent_id: int | None = None,
            is_directory: bool = False,
            file_type: str | None = None,
            mime_type: str | None = None,
            size: int = 0,
            source: str = 'USER',
    ) -> File: ...

    def update(
            self,
            file_id: int,
            name: str,
            path: str,
            parent_id: int | None,
            is_directory: bool,
            file_type: str | None,
            mime_type: str | None,
            size: int,
    ) -> File | None: ...

    def update_size(self, file_id: int, size: int) -> File | None: ...

    def delete(self, file_id: int) -> bool: ...


class SkillsRepository(Protocol):
    def list_active(self) -> list[Skill]:
        '''Skill đang bật, always_on đứng trước theo sort_order'''

    def list_all(self) -> list[Skill]: ...

    def get_by_id(self, skill_id: int) -> Skill | None: ...

    def create(self, skill: Skill) -> Skill:
        '''Tên trùng thì raise DuplicateRecordError'''

    def update(self, skill: Skill) -> Skill | None:
        '''Ghi đè toàn bộ trường. Tên trùng thì raise DuplicateRecordError'''

    def delete(self, skill_id: int) -> bool:
        '''False nếu không có skill này'''


class ModelsRepository(Protocol):
    def list_all(self) -> list[AIModel]:
        '''Tất cả model kể cả đang tắt, cho trang quản trị'''

    def list_active(self) -> list[AIModel]:
        '''Model đang bật, người dùng được chọn khi chat'''

    def get_by_id(self, model_id: int) -> AIModel | None: ...

    def get_default(self) -> AIModel | None:
        '''Model mặc định đang bật, None nếu chưa đặt hoặc đã bị tắt'''

    def create(self, model: AIModel) -> AIModel:
        '''Trùng provider + model_name thì raise DuplicateRecordError. is_default thì bỏ mặc định ở model khác'''

    def update(self, model: AIModel) -> AIModel | None:
        '''Ghi đè toàn bộ trường, quy tắc như create'''

    def delete(self, model_id: int) -> bool:
        '''False nếu không có model này'''


class MemoriesRepository(Protocol):
    def list_for_prompt(self, user_id: int, limit_per_scope: int = 40) -> list[Memory]:
        '''Memory active để ghép vào system prompt: org + riêng của user'''

    def list_for_extractor(self, user_id: int) -> list[Memory]:
        '''Như list_for_prompt, thêm memory org đang chờ duyệt (để tránh đề xuất trùng)'''

    def list_for_user(self, user_id: int) -> list[Memory]:
        '''Memory riêng của user + đề xuất org do user tạo'''

    def list_org(self, status: str | None = None) -> list[Memory]: ...

    def get_by_id(self, memory_id: int) -> Memory | None: ...

    def create(self, memory: Memory) -> Memory: ...

    def update_content(self, memory_id: int, content: str) -> Memory | None: ...

    def set_status(self, memory_id: int, status: str, approved_by: int | None = None) -> Memory | None: ...


class FeedbacksRepository(Protocol):
    def create(
            self,
            user_id: int,
            conversation_id: int | None,
            content: str,
            rating: int | None = None,
            kind: str | None = None,
    ) -> Feedback: ...

    def mark_processed(self, feedback_id: int) -> None: ...
