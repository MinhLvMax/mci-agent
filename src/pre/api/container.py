from pathlib import Path
from typing import Protocol

from fastapi import Request

from src.app.ports.model_reasoner import ModelReasoner
from src.app.ports.unit_of_work import UnitOfWork
from src.app.services.agent_service import AgentService
from src.app.ports.security import PasswordHasher, TokenService
from src.app.ports.storage import FileStorage, WorkspaceScanner, WorkspaceService
from src.app.services.memory_service import MemoryService
from src.dom.entities.skill import Skill


class ApiContainer(Protocol):
    '''
    Những gì tầng API cần từ bên ngoài. Tầng pre chỉ biết Protocol này,
    còn đối tượng thật do bootstrap lắp ráp và entries_point truyền vào khi tạo app.
    Mọi kiểu trả về đều là port của tầng app, không phải lớp cụ thể ở tầng inf.
    '''

    def unit_of_work(self) -> UnitOfWork:
        '''Phiên làm việc với CSDL, dùng với "with"'''

    def token_service(self) -> TokenService:
        '''Cấp và kiểm tra access token'''

    def password_hasher(self) -> PasswordHasher: ...

    def workspace_service(self) -> WorkspaceService: ...

    def file_storage(self, workspace_root: Path) -> FileStorage:
        '''Đọc/ghi file vật lý, chỉ trong workspace_root'''

    def workspace_scanner(self) -> WorkspaceScanner:
        '''Quét file/thư mục trong workspace để đồng bộ metadata với CSDL'''

    def agent_service(
            self,
            workspace_dir: Path,
            skills: list[Skill],
            memory_service: MemoryService | None = None,
            user_id: int | None = None,
            conversation_id: int | None = None,
    ) -> AgentService: ...

    def title_reasoner(self) -> ModelReasoner:
        '''Model đặt tên hội thoại'''

    def lesson_reasoner(self) -> ModelReasoner:
        '''Model rút bài học sau mỗi lượt chat/góp ý'''


def get_container(request: Request) -> ApiContainer:
    '''Dependency: lấy container mà create_app đã gắn vào app'''
    return request.app.state.container
