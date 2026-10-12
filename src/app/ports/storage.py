from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class FileStorage(Protocol):
    '''
    Đọc/ghi file vật lý trong một workspace. Đường dẫn là đường dẫn tương đối trong workspace,
    adapter phải chặn mọi truy cập ra ngoài workspace.
    '''

    def read(self, path: str) -> Any:
        '''Đọc và parse theo loại file (json -> dict, csv -> list[dict], còn lại -> str)'''

    def write(self, path: str, content: Any, overwrite: bool = True) -> Path: ...

    def write_bytes_unique(self, filename: str, data: bytes) -> str:
        '''Ghi file, trùng tên thì tự đổi tên. Trả về đường dẫn thực tế đã dùng'''

    def delete(self, path: str) -> bool: ...

    def exists(self, path: str) -> bool: ...

    def get_path(self, path: str) -> Path:
        '''Đường dẫn vật lý để gửi file cho client'''

    def zip_directory(self, path: str) -> Path:
        '''Nén thư mục thành file zip tạm, bên gọi tự xoá sau khi dùng'''

    def get_size(self, path: str) -> int: ...

    def get_mime_type(self, path: str) -> str | None: ...

    def get_file_type(self, path: str) -> str: ...


class FileStorageFactory(Protocol):
    def __call__(self, workspace_root: Path) -> FileStorage: ...


class WorkspaceService(Protocol):
    '''Thư mục làm việc vật lý của từng user/conversation'''

    def get_conversation_workspace(self, user_id: int, conversation_id: int) -> Path:
        '''Chưa có thì tạo'''

    def delete_conversation_workspace(self, user_id: int, conversation_id: int) -> bool: ...


@dataclass(frozen=True)
class WorkspaceEntry:
    '''Một file/thư mục đang có thật trong workspace, đã đọc sẵn metadata'''
    path: str  # Đường dẫn tương đối tính từ workspace, dạng "reports/result.md"
    name: str
    parent_path: str | None  # None nếu nằm ngay trong workspace
    is_directory: bool
    file_type: str | None  # Đuôi file viết thường không có dấu chấm ("md", "json"), thư mục là None
    mime_type: str | None
    size: int  # Thư mục là 0


class WorkspaceScanner(Protocol):
    def scan(self, workspace_dir: Path) -> list[WorkspaceEntry]:
        '''
        Mọi file/thư mục trong workspace, thư mục cha luôn đứng trước con.
        Workspace không tồn tại thì FileNotFoundError, không phải thư mục thì NotADirectoryError.
        '''
