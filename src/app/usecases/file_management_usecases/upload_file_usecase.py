from dataclasses import dataclass

from src.app.ports.repositories import FilesRepository
from src.app.ports.storage import FileStorage

from src.dom.entities.file import File


@dataclass
class UploadFileCommand:
    conversation_id: int
    filename: str  # Tên file gốc trên máy người dùng, chưa được làm sạch
    content: bytes  # Nguyên nội dung file


@dataclass
class UploadFileResult:
    file: File  # Metadata của file vừa được lưu


class UploadFileUseCase:

    def __init__(
            self,
            files_repository: FilesRepository,
            file_storage: FileStorage,
    ):
        self.files_repository = files_repository
        self.file_storage = file_storage

    def execute(
            self,
            command: UploadFileCommand
    ) -> UploadFileResult:
        """
        Lưu file người dùng upload gồm 2 phần:

        1. Ghi file vật lý vào thư mục gốc workspace (tự đổi tên nếu trùng).
        2. Tạo metadata trong PostgreSQL với source = USER.
        """

        saved_path = self.file_storage.write_bytes_unique(  # Ghi file, nhận lại tên thực tế đã dùng
            filename=command.filename,
            data=command.content,
        )

        try:
            file = self.files_repository.create(  # Đăng ký metadata cho file vừa ghi
                conversation_id=command.conversation_id,
                name=saved_path,  # File nằm ở thư mục gốc nên tên trùng với path
                path=saved_path,  # Relative path tính từ workspace
                parent_id=None,  # Thư mục gốc không có thư mục cha
                is_directory=False,
                file_type=self.file_storage.get_file_type(saved_path) or None,  # Đuôi file, None nếu không có đuôi
                mime_type=self.file_storage.get_mime_type(saved_path),  # Đoán MIME theo đuôi file
                size=len(command.content),  # Kích thước tính bằng byte
                source="USER",  # Đánh dấu file do người dùng đưa vào, không phải Agent
            )

        except Exception:
            self.file_storage.delete(saved_path)  # Lưu metadata lỗi thì xóa file để không còn file mồ côi
            raise  # Báo lỗi lên router

        return UploadFileResult(
            file=file
        )
